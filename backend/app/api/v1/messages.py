"""Messaging endpoints.

Access rules, all enforced in `MessagingService`:

- Only a participant sees a conversation. Not even an administrator without
  participation reads other people's correspondence.
- A client user only ever sees `cliente` conversations about their own client
  record. An internal thread is unreachable from the portal whatever the id.
- Message bodies never enter the audit log.
"""

import re
from datetime import datetime
from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session, get_user_permission_names, get_user_scope, require_permission
from app.core.config import get_settings
from app.core.http_status import (
    HTTP_413_CONTENT_TOO_LARGE,
    HTTP_422_UNPROCESSABLE,
)
from app.models import Conversation, Message, MessageAttachment, User
from app.schemas.messaging import (
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
    MessageAttachmentResponse,
    MessageResponse,
    NotificationResponse,
    ParticipantOptionResponse,
    ParticipantResponse,
    ThreadResponse,
    UnreadSummaryResponse,
)
from app.services.cases import CaseScope, case_scoped, scope_filter
from app.services.messaging import (
    AttachmentInput,
    ConversationStatus,
    ConversationSummary,
    ConversationType,
    MessageError,
    MessagingService,
)
from app.services.uploads import MAX_UPLOAD_BYTES

router = APIRouter(tags=["messages"])

_SAFE_FILE_NAME = re.compile(r"[^A-Za-z0-9._-]")


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="No encontrado"
    )


async def _scope_clause(
    session: AsyncSession, actor: User, scope: CaseScope
) -> ColumnElement[bool] | None:
    """What the caller may see of the conversation book.

    `None` means everything, which is what `CaseScope.ALL` resolves to.

    A conversation carrying a `case_id` is bound to that expediente and is
    filtered on it. A conversation with **no** `case_id` is firm-wide, and stays
    visible to whoever holds `messages:read`. That is a deliberate decision
    rather than an oversight: internal notes with no expediente attached are
    ordinary practice, and `test_staff_drafts_but_neither_issues_nor_voids`
    showed what happens when a scope filter answers "no existe" where the truth
    is "that one is not yours, this one is".

    `case_scoped` drops NULL rows, so they are ORed back here. Pinned by
    `test_a_thread_without_a_case_stays_readable` so tightening later is a
    visible decision.
    """
    clause = case_scoped(Conversation.case_id, await scope_filter(session, actor, scope))
    if clause is None:
        return None
    return or_(Conversation.case_id.is_(None), clause)


def _attachment_disposition(file_name: str) -> str:
    safe = _SAFE_FILE_NAME.sub("_", file_name).strip("._") or "adjunto"
    return f"attachment; filename=\"{safe}\"; filename*=UTF-8''{quote(safe, safe='')}"


def _conversation_response(summary: ConversationSummary) -> ConversationResponse:
    conversation = summary.conversation
    return ConversationResponse(
        id=conversation.id,
        subject=conversation.subject,
        conversation_type=conversation.conversation_type,
        status=conversation.status,
        case_id=conversation.case_id,
        case_number=conversation.case.case_number if conversation.case else None,
        client_id=conversation.client_id,
        message_count=conversation.message_count,
        unread=summary.unread,
        last_message_preview=conversation.last_message_preview,
        last_message_at=conversation.last_message_at,
        participant_count=len(conversation.participants),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


def _participant_name(user: User | None) -> str:
    if user is None:
        return "Cuenta eliminada"
    return user.full_name or user.email


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("messages:read"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    case_id: Annotated[UUID | None, Query()] = None,
    conversation_type: Annotated[str | None, Query()] = None,
    only_unread: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ConversationResponse]:
    """Conversations the caller takes part in, most recently active first."""
    clause = await _scope_clause(session, actor, scope)
    summaries = await MessagingService(session).list_conversations(
        actor,
        scope_clause=clause,
        case_id=case_id,
        conversation_type=(
            ConversationType(conversation_type) if conversation_type else None
        ),
        only_unread=only_unread,
        limit=limit,
    )
    return [_conversation_response(summary) for summary in summaries]


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    payload: ConversationCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("messages:create_conversation"))],
) -> ConversationResponse:
    """Open a conversation. Only staff can: a client never opens a thread."""
    service = MessagingService(session)
    try:
        conversation = await service.create_conversation(
            actor,
            subject=payload.subject,
            conversation_type=ConversationType(payload.conversation_type),
            case_id=payload.case_id,
            client_id=payload.client_id,
            participant_ids=payload.participant_ids,
        )
    except MessageError as error:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE, detail=str(error)
        ) from error

    await session.commit()
    fresh = await service.get_conversation(conversation.id, actor)
    assert fresh is not None
    return _conversation_response(ConversationSummary(conversation=fresh, unread=0))


@router.get(
    "/conversations/participant-options",
    response_model=list[ParticipantOptionResponse],
)
async def participant_options(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("messages:create_conversation"))],
    conversation_type: Annotated[ConversationType, Query()] = ConversationType.INTERNAL,
    client_id: Annotated[UUID | None, Query()] = None,
) -> list[ParticipantOptionResponse]:
    del actor
    options = await MessagingService(session).participant_options(
        conversation_type=conversation_type,
        client_id=client_id,
    )
    return [
        ParticipantOptionResponse(
            id=option.user.id,
            display_name=_participant_name(option.user),
            account_type=option.account_type,
            client_id=option.client_id,
        )
        for option in options
    ]


@router.get("/conversations/{conversation_id}", response_model=ThreadResponse)
async def get_thread(
    conversation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("messages:read"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    before: Annotated[datetime | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ThreadResponse:
    """One conversation with its messages. Reading marks the thread as read."""
    clause = await _scope_clause(session, actor, scope)
    service = MessagingService(session)
    conversation = await service.get_conversation(conversation_id, actor, scope_clause=clause)
    if conversation is None:
        raise _not_found()

    messages = await service.list_messages(
        conversation_id, actor, scope_clause=clause, before=before, limit=limit
    )
    participant = await service.participant(conversation_id, actor.id)
    unread = await service.unread_count(conversation_id, participant.last_read_at)
    await service.mark_read(conversation_id, actor)
    await session.commit()

    fresh = await service.get_conversation(conversation_id, actor)
    assert fresh is not None
    participant_users = {
        user.id: user
        for user in (
            await session.execute(
                select(User).where(
                    User.id.in_([item.user_id for item in fresh.participants])
                )
            )
        ).scalars().all()
    }
    return ThreadResponse(
        conversation=_conversation_response(
            ConversationSummary(conversation=fresh, unread=unread)
        ),
        participants=[
            ParticipantResponse(
                id=item.id,
                user_id=item.user_id,
                display_name=_participant_name(participant_users.get(item.user_id)),
                role=item.role,
                joined_at=item.joined_at,
                last_read_at=item.last_read_at,
                is_muted=item.is_muted,
            )
            for item in fresh.participants
            if item.left_at is None
        ],
        messages=[await _message_response(session, message) for message in messages],
        unread=unread,
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("messages:manage_participants"))],
) -> ConversationResponse:
    service = MessagingService(session)
    conversation = await service.get_conversation(conversation_id, actor)
    if conversation is None:
        raise _not_found()

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE,
            detail="No se envió ningún campo a modificar",
        )
    for field, value in data.items():
        setattr(conversation, field, value)
    await session.commit()

    fresh = await service.get_conversation(conversation_id, actor)
    assert fresh is not None
    return _conversation_response(ConversationSummary(conversation=fresh))


@router.post(
    "/conversations/{conversation_id}/participants",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_participant(
    conversation_id: UUID,
    participant_id: Annotated[UUID, Query(alias="user_id")],
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("messages:manage_participants"))],
) -> ConversationResponse:
    """Add someone to a conversation.

    Refused, not ignored, when the target is a client user and the thread is
    internal: silently doing nothing would leave the caller thinking an internal
    colleague had been notified.
    """
    service = MessagingService(session)
    conversation = await service.get_conversation(conversation_id, actor)
    if conversation is None:
        raise _not_found()

    try:
        await service.add_participant(
            conversation,
            participant_id,
            ConversationType(conversation.conversation_type),
            actor,
        )
    except MessageError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error

    await session.commit()
    fresh = await service.get_conversation(conversation_id, actor)
    assert fresh is not None
    return _conversation_response(ConversationSummary(conversation=fresh))


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    conversation_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("messages:send"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
    body: Annotated[str, Form(max_length=5000)],
    files: Annotated[list[UploadFile], File()] = [],  # noqa: B006
) -> MessageResponse:
    """Send a message, optionally with attachments.

    The body arrives as form data because attachments require multipart; the
    service still refuses an empty or oversized message.

    Count and size are checked **before** a single byte is read. Reading first
    and validating afterwards meant five 10 MB files were 50 MB resident before
    anyone noticed there were too many of them, which is the cheapest way to
    exhaust a process that has no other guard. `read(cap + 1)` bounds what a
    single oversized file can cost, the same pattern the media endpoint uses.
    """
    clause = await _scope_clause(session, actor, scope)
    service = MessagingService(session)
    conversation = await service.get_conversation(conversation_id, actor, scope_clause=clause)
    if conversation is None:
        raise _not_found()

    settings = get_settings()
    named = [upload for upload in files if upload.filename]

    if len(named) > settings.max_attachments_per_message:
        raise HTTPException(
            status_code=HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"Se admiten hasta {settings.max_attachments_per_message} "
                "archivos por mensaje"
            ),
        )

    cap = min(settings.max_attachment_bytes, MAX_UPLOAD_BYTES)
    attachments: list[AttachmentInput] = []
    for upload in named:
        content = await upload.read(cap + 1)
        if len(content) > cap:
            raise HTTPException(
                status_code=HTTP_413_CONTENT_TOO_LARGE,
                detail=f"«{upload.filename}» supera el máximo de {cap} bytes",
            )
        attachments.append(
            AttachmentInput(
                filename=upload.filename or "adjunto",
                content=content,
                declared_mime=upload.content_type,
            )
        )
    if attachments and "messages:attach" not in get_user_permission_names(actor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tiene permiso para adjuntar archivos",
        )

    try:
        message = await service.send_message(
            conversation, actor, body, attachments=attachments
        )
    except MessageError as error:
        raise HTTPException(
            status_code=HTTP_422_UNPROCESSABLE, detail=str(error)
        ) from error

    await session.commit()
    return await _message_response(session, message)


@router.get("/messages/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("messages:read"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> MessageResponse:
    clause = await _scope_clause(session, actor, scope)
    service = MessagingService(session)
    message = await session.get(Message, message_id)
    if message is None or message.deleted_at is not None:
        raise _not_found()
    conversation = await service.get_conversation(
        message.conversation_id, actor, scope_clause=clause
    )
    if conversation is None:
        raise _not_found()
    return await _message_response(session, message)


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("messages:archive"))],
) -> Response:
    service = MessagingService(session)
    message = await session.get(Message, message_id)
    if message is None:
        raise _not_found()
    conversation = await service.get_conversation(message.conversation_id, actor)
    if conversation is None:
        raise _not_found()

    try:
        await service.delete_message(message, actor)
    except MessageError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(error)
        ) from error

    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/messages/attachments/{attachment_id}",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def download_attachment(
    attachment_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("messages:read"))],
    scope: Annotated[CaseScope, Depends(get_user_scope)],
) -> Response:
    """Download an attachment. Always served as an attachment, never inline."""
    result = await session.execute(
        select(MessageAttachment).where(MessageAttachment.id == attachment_id)
    )
    attachment = result.scalars().first()
    if attachment is None:
        raise _not_found()

    clause = await _scope_clause(session, actor, scope)
    service = MessagingService(session)
    try:
        found, content = await service.read_attachment(
            attachment.message_id, attachment.id, actor, scope_clause=clause
        )
    except MessageError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error

    return Response(
        content=content,
        media_type=found.mime_type,
        headers={
            "Content-Disposition": _attachment_disposition(found.original_filename),
            "X-Content-SHA256": found.sha256,
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("notifications:read"))],
    only_unread: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[NotificationResponse]:
    """The caller's own notifications. Nobody can read anybody else's."""
    items = await MessagingService(session).list_notifications(
        actor, only_unread=only_unread, limit=limit
    )
    return [NotificationResponse.model_validate(item) for item in items]


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationResponse,
)
async def mark_notification_read(
    notification_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("notifications:read"))],
) -> NotificationResponse:
    service = MessagingService(session)
    try:
        notification = await service.mark_notification_read(notification_id, actor)
    except MessageError as error:
        raise _not_found() from error
    await session.commit()
    return NotificationResponse.model_validate(notification)


@router.post("/notifications/read-all", response_model=UnreadSummaryResponse)
async def mark_all_notifications_read(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("notifications:read"))],
) -> UnreadSummaryResponse:
    service = MessagingService(session)
    await service.mark_all_notifications_read(actor)
    await session.commit()
    return UnreadSummaryResponse(
        unread_messages=await service.total_unread(actor), unread_notifications=0
    )


@router.get("/messages/unread/summary", response_model=UnreadSummaryResponse)
async def unread_summary(
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_permission("messages:read"))],
) -> UnreadSummaryResponse:
    """Pending messages and notifications. Feeds the dashboards."""
    service = MessagingService(session)
    return UnreadSummaryResponse(
        unread_messages=await service.total_unread(actor),
        unread_notifications=await service.unread_notifications(actor),
    )


async def _message_response(
    session: AsyncSession, message: Message
) -> MessageResponse:
    result = await session.execute(
        select(MessageAttachment)
        .where(MessageAttachment.message_id == message.id)
        .order_by(MessageAttachment.created_at)
    )
    attachments = [] if message.deleted_at else [
        MessageAttachmentResponse.model_validate(item) for item in result.scalars().all()
    ]
    sender = await session.get(User, message.sender_id) if message.sender_id else None
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        sender_id=message.sender_id,
        sender_name="Sistema" if message.is_system else _participant_name(sender),
        body="" if message.deleted_at else message.body,
        is_system=message.is_system,
        sent_at=message.sent_at,
        edited_at=message.edited_at,
        deleted_at=message.deleted_at,
        attachments=attachments,
    )


__all__ = ["ConversationStatus", "router"]
