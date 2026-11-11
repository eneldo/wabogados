"""Internal and client messaging.

`MASTER_PROMPT` section 33 asks for internal messaging that can be linked to a
client or a case, with a read state and basic audit. The hard part is not the
thread, it is the boundary between a conversation the firm uses internally and
one the client portal may see.

The boundary rules, all enforced in the service rather than in the endpoints:

- A client user can only ever see conversations of type ``cliente`` whose
  ``client_id`` is their own client record. An ``interna`` conversation is never
  reachable from the portal, whatever the identifier.
- A client is never added as a participant of an internal conversation, and the
  service refuses the attempt instead of ignoring it.
- Staff see a conversation when they participate in it, or when it belongs to a
  case they are assigned to.
- Nobody reads a conversation they are not a member of, including an
  administrator without case scope. Administering the platform is not the same as
  reading other people's correspondence.

Message bodies never reach the audit log. The trail records that a message was
sent, by whom and when; copying the body would turn the audit table into an
uncontrolled copy of the firm's private correspondence.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_user_permission_names
from app.core.config import get_settings
from app.core.constants import StorageTier
from app.models import (
    Case,
    Client,
    Conversation,
    ConversationParticipant,
    Message,
    MessageAttachment,
    Notification,
    User,
)
from app.services.cases import case_scoped, resolve_scope, scope_filter
from app.services.history import record_changes
from app.services.storage import (
    StorageBackend,
    StorageError,
    build_message_key,
    build_storage,
)
from app.services.uploads import (
    MAX_UPLOAD_BYTES,
    UploadValidationError,
    validate_upload,
)

logger = logging.getLogger(__name__)

CONVERSATION_ENTITY = "conversations"
MESSAGE_ENTITY = "messages"

PREVIEW_LENGTH = 200


class MessageError(Exception):
    """Raised when a messaging operation is refused."""


class ConversationType(StrEnum):
    INTERNAL = "interna"
    CLIENT = "cliente"


class ConversationStatus(StrEnum):
    OPEN = "abierto"
    CLOSED = "cerrado"


class NotificationType(StrEnum):
    NEW_MESSAGE = "new_message"
    NEW_CONVERSATION = "new_conversation"
    CASE_UPDATE = "case_update"
    EVIDENCE_PUBLISHED = "evidence_published"
    DOCUMENT_PUBLISHED = "document_published"
    HEARING_SCHEDULED = "hearing_scheduled"
    DEADLINE = "deadline"


@dataclass(frozen=True)
class AttachmentInput:
    """One file to attach, already read into memory by the endpoint."""

    filename: str
    content: bytes
    declared_mime: str | None = None


@dataclass
class ConversationSummary:
    """A conversation as it appears in a list."""

    conversation: Conversation
    unread: int = 0
    is_participant: bool = False


@dataclass(frozen=True)
class ParticipantOption:
    user: User
    account_type: str
    client_id: UUID | None = None


class MessagingService:
    """Conversations, messages, attachments and notifications."""

    def __init__(
        self, session: AsyncSession, storage: StorageBackend | None = None
    ) -> None:
        self.session = session
        self.settings = get_settings()
        if storage is not None:
            self.storage = storage
        else:
            self.storage = build_storage(self.settings)

    # -- scope --------------------------------------------------------------

    def _own_client_ids(self, user: User) -> ColumnElement[bool] | None:
        """Restrict to conversations about the caller's own client record."""
        return Conversation.client_id == func.coalesce(
            select(Client.id).where(Client.user_id == user.id).scalar_subquery(),
            select(func.null()),
        )

    def _visibility_clause(self, user: User) -> ColumnElement[bool]:
        """Coarse conversation-type filter for listings.

        Case scope is applied separately by the caller via ``scope_clause``; this
        method only distinguishes staff-capable accounts from the client portal.
        A client only ever sees their own ``cliente`` conversations.
        """
        permissions = get_user_permission_names(user)
        if "messages:create_conversation" in permissions or user.is_superuser:
            return Conversation.conversation_type.in_(
                (ConversationType.INTERNAL.value, ConversationType.CLIENT.value)
            )
        # Portal: published channel only.
        return Conversation.conversation_type == ConversationType.CLIENT.value

    async def _client_ids_for(self, user: User) -> list[UUID]:
        result = await self.session.execute(
            select(Client.id).where(
                Client.user_id == user.id,
                Client.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    def _is_client_portal(self, user: User) -> bool:
        return any(role.name == "cliente" for role in user.roles)

    # -- conversations ------------------------------------------------------

    async def create_conversation(
        self,
        actor: User,
        *,
        subject: str,
        conversation_type: ConversationType = ConversationType.INTERNAL,
        case_id: UUID | None = None,
        client_id: UUID | None = None,
        participant_ids: list[UUID] | None = None,
    ) -> Conversation:
        """Open a conversation and register its participants."""
        if conversation_type is ConversationType.CLIENT and client_id is None:
            raise MessageError("Una conversación de cliente necesita un cliente")

        if case_id is not None:
            scope = await resolve_scope(self.session, actor)
            scoped = await scope_filter(self.session, actor, scope)
            filters: list[ColumnElement[bool]] = [
                Case.id == case_id,
                Case.is_active.is_(True),
            ]
            if scoped is not None:
                filters.append(scoped)
            case = (
                await self.session.execute(select(Case).where(*filters))
            ).scalar_one_or_none()
            if case is None:
                raise MessageError("El expediente no existe o no está disponible")
        else:
            case = None

        if client_id is not None:
            client = await self.session.get(Client, client_id)
            if client is None or not client.is_active:
                raise MessageError("El cliente no existe")
            if case is not None and case.client_id != client_id:
                raise MessageError("El expediente no pertenece al cliente indicado")

        conversation = Conversation(
            subject=subject[:255],
            conversation_type=str(conversation_type),
            case_id=case_id,
            client_id=client_id,
            created_by=actor.id,
            status=str(ConversationStatus.OPEN),
            is_active=True,
        )
        self.session.add(conversation)
        await self.session.flush()

        await self._add_participant(
            conversation, actor.id, role="propietario", last_read_at=None
        )
        participant_ids = list(dict.fromkeys(participant_ids or []))
        if conversation_type is ConversationType.CLIENT and client_id is not None:
            portal_users = await self.session.execute(
                select(User.id)
                .join(Client, Client.user_id == User.id)
                .where(
                    Client.id == client_id,
                    Client.is_active.is_(True),
                    User.is_active.is_(True),
                )
            )
            participant_ids.extend(
                user_id
                for user_id in portal_users.scalars().all()
                if user_id not in participant_ids
            )
        for participant_id in participant_ids:
            await self.add_participant(
                conversation, participant_id, conversation_type, actor
            )

        record_changes(
            self.session,
            entity=CONVERSATION_ENTITY,
            entity_id=conversation.id,
            before={},
            after={
                "subject": conversation.subject,
                "conversation_type": conversation.conversation_type,
                "case_id": str(case_id) if case_id else None,
                "client_id": str(client_id) if client_id else None,
            },
            changed_by=actor.id,
            fields=("subject", "conversation_type", "case_id", "client_id"),
        )
        await self.session.flush()
        return conversation

    async def _add_participant(
        self,
        conversation: Conversation,
        user_id: UUID,
        *,
        role: str = "miembro",
        last_read_at: datetime | None = None,
    ) -> ConversationParticipant:
        """Add a membership row, reusing the existing one if it is already there.

        The lookup goes to the database instead of walking
        ``conversation.participants``: that relationship is lazy, and touching it
        outside an awaited context raises MissingGreenlet.
        """
        result = await self.session.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation.id,
                ConversationParticipant.user_id == user_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        participant = ConversationParticipant(
            conversation_id=conversation.id,
            user_id=user_id,
            role=role,
            last_read_at=last_read_at,
        )
        self.session.add(participant)
        await self.session.flush()
        # Repopulate the collection eagerly. Appending to it, or reading from it,
        # would fire a lazy load outside an awaited ORM context and raise
        # MissingGreenlet.
        await self.session.refresh(conversation, ["participants"])
        return participant

    async def add_participant(
        self,
        conversation: Conversation,
        user_id: UUID,
        conversation_type: ConversationType,
        actor: User,
    ) -> ConversationParticipant | None:
        """Add a participant, refusing to leak an internal thread to the portal."""
        target = await self.session.get(User, user_id)
        if target is None or not target.is_active:
            raise MessageError("El participante no existe o está inactivo")

        target_is_client = self._is_client_portal(target)
        if conversation_type is ConversationType.INTERNAL and target_is_client:
            # Silently ignoring this would leave the caller believing the
            # internal team had been notified.
            raise MessageError(
                "No se puede añadir a un usuario de cliente a una conversación "
                "interna"
            )

        if conversation_type is ConversationType.CLIENT and target_is_client:
            target_clients = await self._client_ids_for(target)
            if conversation.client_id not in target_clients:
                raise MessageError(
                    "El usuario de cliente no pertenece al cliente de la conversación"
                )

        if not target_is_client and not target.is_superuser:
            permissions = get_user_permission_names(target)
            if "messages:read" not in permissions:
                raise MessageError("El participante no tiene acceso a mensajería")

        existing = await self.session.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation.id,
                ConversationParticipant.user_id == user_id,
            )
        )
        found = existing.scalar_one_or_none()
        if found is not None:
            return found

        if conversation.status == ConversationStatus.CLOSED.value:
            raise MessageError("No se pueden añadir participantes a un hilo cerrado")

        participant = await self._add_participant(conversation, user_id)
        await self.session.flush()

        await self.notify(
            target,
            NotificationType.NEW_CONVERSATION,
            title=f"Nueva conversación: {conversation.subject}",
            body="Se le ha añadido a una conversación.",
            entity=CONVERSATION_ENTITY,
            entity_id=conversation.id,
        )
        record_changes(
            self.session,
            entity=CONVERSATION_ENTITY,
            entity_id=conversation.id,
            before={},
            after={"participant_id": str(user_id)},
            changed_by=actor.id,
            fields=("participant_id",),
            reason="Participante añadido",
        )
        return participant

    def _scope_clause(self, scope_clause: ColumnElement[bool] | None) -> ColumnElement[bool] | None:
        """Build the case scope restriction for conversations.

        `None` means no restriction (CaseScope.ALL). Otherwise we allow:
        - Conversations with no `case_id` (firm-wide material)
        - Conversations whose `case_id` is in the caller's scope

        `case_scoped` drops NULL rows, so they are ORed back here.
        """
        if scope_clause is None:
            return None
        restricted = case_scoped(Conversation.case_id, scope_clause)
        if restricted is None:
            # Inalcanzable hoy: `case_scoped` solo es None cuando la cláusula
            # lo es, y esa rama se descartó arriba. Se anota como rama
            # explícita para que `or_` nunca reciba None.
            return None
        return or_(Conversation.case_id.is_(None), restricted)

    async def get_conversation(
        self,
        conversation_id: UUID,
        user: User,
        *,
        scope_clause: ColumnElement[bool] | None = None,
    ) -> Conversation | None:
        """Return a conversation only if the caller takes part in it.

        Membership is a join against the participants table, not an attribute
        read: an attribute read would rely on the relationship being loaded and
        would let a caller see the thread they were never added to.

        `scope_clause` restricts the visible conversations to those whose
        `case_id` falls inside the caller's scope (or is NULL for firm-wide).
        """
        filters: list[ColumnElement[bool]] = [
            Conversation.id == conversation_id,
            Conversation.is_active.is_(True),
            ConversationParticipant.user_id == user.id,
            ConversationParticipant.left_at.is_(None),
        ]
        clause = self._scope_clause(scope_clause)
        if clause is not None:
            filters.append(clause)
        if self._is_client_portal(user):
            own = await self._client_ids_for(user)
            if not own:
                return None
            filters.extend(
                [
                    Conversation.conversation_type == ConversationType.CLIENT.value,
                    Conversation.client_id.in_(own),
                ]
            )
        result = await self.session.execute(
            select(Conversation)
            .join(
                ConversationParticipant,
                ConversationParticipant.conversation_id == Conversation.id,
            )
            .options(selectinload(Conversation.participants))
            .where(*filters)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def participant_options(
        self,
        *,
        conversation_type: ConversationType,
        client_id: UUID | None = None,
    ) -> list[ParticipantOption]:
        """Active accounts eligible for the selected security boundary."""
        result = await self.session.execute(
            select(User).options(selectinload(User.roles)).where(User.is_active.is_(True))
        )
        options: list[ParticipantOption] = []
        for user in result.scalars().unique().all():
            if self._is_client_portal(user):
                if conversation_type is ConversationType.INTERNAL or client_id is None:
                    continue
                client_ids = await self._client_ids_for(user)
                if client_id not in client_ids:
                    continue
                options.append(
                    ParticipantOption(user, ConversationType.CLIENT.value, client_id)
                )
                continue
            if user.is_superuser or "messages:read" in get_user_permission_names(user):
                options.append(ParticipantOption(user, "personal"))
        return sorted(
            options,
            key=lambda option: (option.user.full_name or option.user.email).casefold(),
        )

    async def list_conversations(
        self,
        user: User,
        *,
        scope_clause: ColumnElement[bool] | None = None,
        case_id: UUID | None = None,
        conversation_type: ConversationType | None = None,
        only_unread: bool = False,
        limit: int = 50,
    ) -> list[ConversationSummary]:
        """Conversations visible to the caller, most recently active first."""
        filters: list[ColumnElement[bool]] = [
            Conversation.is_active.is_(True),
            self._visibility_clause(user),
            ConversationParticipant.user_id == user.id,
            ConversationParticipant.left_at.is_(None),
        ]
        clause = self._scope_clause(scope_clause)
        if clause is not None:
            filters.append(clause)

        if self._is_client_portal(user):
            own = await self._client_ids_for(user)
            if not own:
                return []
            filters.append(Conversation.client_id.in_(own))

        if conversation_type is not None:
            filters.append(Conversation.conversation_type == str(conversation_type))

        if case_id is not None:
            filters.append(Conversation.case_id == case_id)

        result = await self.session.execute(
            select(Conversation, ConversationParticipant.last_read_at)
            .join(
                ConversationParticipant,
                (ConversationParticipant.conversation_id == Conversation.id)
                & (ConversationParticipant.user_id == user.id),
            )
            .where(*filters)
            .order_by(
                func.coalesce(Conversation.last_message_at, Conversation.created_at).desc()
            )
            .limit(limit)
        )

        summaries: list[ConversationSummary] = []
        for conversation, last_read_at in result.all():
            unread = await self.unread_count(conversation.id, last_read_at)
            if only_unread and unread == 0:
                continue
            summaries.append(
                ConversationSummary(
                    conversation=conversation,
                    unread=unread,
                    is_participant=True,
                )
            )
        return summaries

    async def unread_count(
        self, conversation_id: UUID, last_read_at: datetime | None
    ) -> int:
        """Messages sent after this participant's read marker."""
        statement = select(func.count()).select_from(Message).where(
            Message.conversation_id == conversation_id,
            Message.deleted_at.is_(None),
        )
        if last_read_at is not None:
            statement = statement.where(Message.sent_at > last_read_at)
        result = await self.session.execute(statement)
        return int(result.scalar_one() or 0)

    async def total_unread(self, user: User) -> int:
        """Unread messages across every conversation. Feeds the dashboards."""
        result = await self.session.execute(
            select(Message.id)
            .join(
                Conversation,
                Message.conversation_id == Conversation.id,
            )
            .join(
                ConversationParticipant,
                (ConversationParticipant.conversation_id == Conversation.id)
                & (ConversationParticipant.user_id == user.id),
            )
            .where(
                Conversation.is_active.is_(True),
                ConversationParticipant.left_at.is_(None),
                Message.deleted_at.is_(None),
                or_(
                    ConversationParticipant.last_read_at.is_(None),
                    Message.sent_at > ConversationParticipant.last_read_at,
                ),
            )
        )
        return len(result.all())

    async def mark_read(self, conversation_id: UUID, user: User) -> ConversationParticipant:
        participant = await self.participant(conversation_id, user.id)
        participant.last_read_at = datetime.now(UTC)
        await self.session.flush()
        return participant

    async def participant(
        self, conversation_id: UUID, user_id: UUID
    ) -> ConversationParticipant:
        result = await self.session.execute(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id,
                ConversationParticipant.left_at.is_(None),
            )
        )
        participant = result.scalar_one_or_none()
        if participant is None:
            raise MessageError("No participa en esa conversación")
        return participant

    # -- messages -----------------------------------------------------------

    async def send_message(
        self,
        conversation: Conversation,
        actor: User,
        body: str,
        *,
        attachments: list[AttachmentInput] | None = None,
        notify_participants: bool = True,
    ) -> Message:
        """Append a message to a conversation the sender takes part in."""
        cleaned = body.strip()
        if not cleaned:
            raise MessageError("El mensaje no puede estar vacío")
        if len(cleaned) > 5000:
            raise MessageError("El mensaje supera los 5000 caracteres")

        if conversation.status == ConversationStatus.CLOSED.value:
            raise MessageError("La conversación está cerrada")

        await self.participant(conversation.id, actor.id)

        attachments = attachments or []
        if len(attachments) > self.settings.max_attachments_per_message:
            raise MessageError(
                f"Máximo {self.settings.max_attachments_per_message} archivos por "
                "mensaje"
            )

        stored: list[tuple[AttachmentInput, str, str, str]] = []
        for attachment in attachments:
            stored.append(await self._validate_attachment(attachment))

        message = Message(
            conversation_id=conversation.id,
            sender_id=actor.id,
            body=cleaned,
        )
        self.session.add(message)
        await self.session.flush()

        for attachment, key, mime, digest in stored:
            self.session.add(
                MessageAttachment(
                    message_id=message.id,
                    conversation_id=conversation.id,
                    storage_key=key,
                    original_filename=attachment.filename[:255],
                    mime_type=mime,
                    size_bytes=len(attachment.content),
                    sha256=digest,
                    created_by=actor.id,
                )
            )

        now = datetime.now(UTC)
        conversation.last_message_at = now
        conversation.last_message_preview = cleaned[:PREVIEW_LENGTH]
        conversation.message_count += 1

        # The sender has, by definition, read their own message.
        participant = await self.participant(conversation.id, actor.id)
        participant.last_read_at = now

        # The audit trail records the act, never the content.
        record_changes(
            self.session,
            entity=MESSAGE_ENTITY,
            entity_id=message.id,
            before={},
            after={
                "conversation_id": str(conversation.id),
                "length": len(cleaned),
                "attachments": len(stored),
            },
            changed_by=actor.id,
            fields=("conversation_id", "body", "attachments"),
            reason=f"Mensaje enviado en {conversation.subject}",
        )
        await self.session.flush()

        if notify_participants:
            await self._notify_others(conversation, actor, now)
        return message

    async def _validate_attachment(
        self, attachment: AttachmentInput
    ) -> tuple[AttachmentInput, str, str, str]:
        """Validate and store one attachment. Returns what was persisted."""
        limit = min(self.settings.max_attachment_bytes, MAX_UPLOAD_BYTES)
        if len(attachment.content) > limit:
            raise MessageError(f"El adjunto supera el máximo de {limit} bytes")

        try:
            validated = validate_upload(
                attachment.content, attachment.filename, attachment.declared_mime
            )
        except UploadValidationError as error:
            raise MessageError(str(error)) from error

        key = build_message_key(uuid4(), uuid4(), validated.extension)
        try:
            stored = await self.storage.write(key, attachment.content)
        except StorageError as error:
            raise MessageError(str(error)) from error

        if stored.sha256 != validated.sha256:
            await self.storage.delete(key)
            raise MessageError("El almacenamiento no devolvió el contenido esperado")

        return attachment, key, validated.mime_type, validated.sha256

    async def _notify_others(
        self, conversation: Conversation, sender: User, sent_at: datetime
    ) -> None:
        for participant in conversation.participants:
            if participant.user_id == sender.id or participant.left_at is not None:
                continue
            if participant.is_muted:
                continue
            await self.notify(
                await self.session.get(User, participant.user_id),
                NotificationType.NEW_MESSAGE,
                title=f"Nuevo mensaje en {conversation.subject}",
                entity=CONVERSATION_ENTITY,
                entity_id=conversation.id,
            )
        del sent_at

    async def list_messages(
        self,
        conversation_id: UUID,
        user: User,
        *,
        scope_clause: ColumnElement[bool] | None = None,
        before: datetime | None = None,
        limit: int = 50,
    ) -> list[Message]:
        """The thread, oldest first, paginated backwards from `before`."""
        await self.participant(conversation_id, user.id)
        clause = self._scope_clause(scope_clause)
        if clause is not None:
            # Verify the conversation's case_id is in scope
            conversation = await self.get_conversation(
                conversation_id, user, scope_clause=scope_clause
            )
            if conversation is None:
                raise MessageError("No participa en esa conversación")

        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.sent_at.desc(), Message.id.desc())
            .limit(limit)
        )
        if before is not None:
            statement = statement.where(Message.sent_at < before)

        result = await self.session.execute(statement)
        return list(reversed(result.scalars().all()))

    async def attachments_of(self, message_id: UUID) -> list[MessageAttachment]:
        result = await self.session.execute(
            select(MessageAttachment)
            .where(MessageAttachment.message_id == message_id)
            .order_by(MessageAttachment.created_at)
        )
        return list(result.scalars().all())

    async def read_attachment(
        self,
        message_id: UUID,
        attachment_id: UUID,
        user: User,
        *,
        scope_clause: ColumnElement[bool] | None = None,
    ) -> tuple[MessageAttachment, bytes]:
        """Read one attachment, verifying its digest before handing it over."""
        result = await self.session.execute(
            select(MessageAttachment).where(
                MessageAttachment.id == attachment_id,
                MessageAttachment.message_id == message_id,
            )
        )
        attachment = result.scalars().first()
        if attachment is None:
            raise MessageError("El adjunto no existe")

        message = await self.session.get(Message, message_id)
        if message is None or message.deleted_at is not None:
            raise MessageError("El mensaje no existe")
        clause = self._scope_clause(scope_clause)
        if clause is not None:
            conversation = await self.get_conversation(
                message.conversation_id, user, scope_clause=scope_clause
            )
            if conversation is None:
                raise MessageError("No participa en esa conversación")
        else:
            await self.participant(message.conversation_id, user.id)

        try:
            content = await self.storage.read(attachment.storage_key)
        except StorageError as error:
            raise MessageError(str(error)) from error

        if hashlib.sha256(content).hexdigest() != attachment.sha256:
            raise MessageError(
                "El contenido del adjunto no coincide con su hash; descarga bloqueada"
            )
        return attachment, content

    async def delete_message(
        self, message: Message, actor: User
    ) -> Message:
        """Soft delete. The thread keeps its shape and the action is auditable."""
        if message.sender_id != actor.id and not actor.is_superuser:
            raise MessageError("Solo puede eliminar sus propios mensajes")
        if message.deleted_at is not None:
            return message

        message.deleted_at = datetime.now(UTC)
        message.deleted_by = actor.id
        record_changes(
            self.session,
            entity=MESSAGE_ENTITY,
            entity_id=message.id,
            before={"deleted_at": None},
            after={"deleted_at": message.deleted_at.isoformat()},
            changed_by=actor.id,
            fields=("deleted_at",),
            reason="Mensaje eliminado",
        )
        await self.session.flush()
        return message

    # -- notifications ------------------------------------------------------

    async def notify(
        self,
        user: User | None,
        notification_type: NotificationType,
        *,
        title: str,
        body: str | None = None,
        entity: str | None = None,
        entity_id: UUID | None = None,
    ) -> Notification | None:
        """Create a notification, silently skipping a missing or muted recipient."""
        if user is None or not user.is_active:
            return None
        notification = Notification(
            user_id=user.id,
            notification_type=str(notification_type),
            title=title[:255],
            body=body,
            entity=entity,
            entity_id=entity_id,
        )
        self.session.add(notification)
        await self.session.flush()
        return notification

    async def list_notifications(
        self, user: User, *, only_unread: bool = False, limit: int = 50
    ) -> list[Notification]:
        statement = select(Notification).where(
            Notification.user_id == user.id
        ).order_by(Notification.created_at.desc())
        if only_unread:
            statement = statement.where(Notification.is_read.is_(False))
        result = await self.session.execute(statement.limit(limit))
        return list(result.scalars().all())

    async def unread_notifications(self, user: User) -> int:
        result = await self.session.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == user.id,
                Notification.is_read.is_(False),
            )
        )
        return int(result.scalar_one() or 0)

    async def mark_notification_read(
        self, notification_id: UUID, user: User
    ) -> Notification:
        """Read one notification. Someone else's notification is not found."""
        result = await self.session.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user.id,
            )
        )
        notification = result.scalars().first()
        if notification is None:
            raise MessageError("La notificación no existe")
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(UTC)
            await self.session.flush()
        return notification

    async def mark_all_notifications_read(self, user: User) -> int:
        result = await self.session.execute(
            select(Notification).where(
                Notification.user_id == user.id,
                Notification.is_read.is_(False),
            )
        )
        unread = list(result.scalars().all())
        now = datetime.now(UTC)
        for notification in unread:
            notification.is_read = True
            notification.read_at = now
        await self.session.flush()
        return len(unread)


# The storage interface is asynchronous; `_validate_attachment` awaits it
# directly so the persisted digest is the one that gets recorded.
__all__ = [
    "CONVERSATION_ENTITY",
    "MESSAGE_ENTITY",
    "AttachmentInput",
    "ConversationStatus",
    "ConversationSummary",
    "ConversationType",
    "MessageError",
    "MessagingService",
    "NotificationType",
    "ParticipantOption",
    "StorageTier",
]
