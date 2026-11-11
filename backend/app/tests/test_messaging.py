"""Messaging tests.

The property that matters most: an internal conversation is invisible to the
portal and to anyone who is not a participant. Every test below is written from
the perspective of someone who should *not* see something.
"""

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.config import get_settings
from app.core.http_status import HTTP_413_CONTENT_TOO_LARGE
from app.models import (
    Case,
    CaseLawyer,
    ChangeLog,
    Client,
    ConversationParticipant,
    Lawyer,
    Message,
    Notification,
    Role,
    User,
)
from app.services.messaging import (
    AttachmentInput,
    ConversationType,
    MessageError,
    MessagingService,
    NotificationType,
)
from app.services.storage import build_message_key
from app.services.storage_local import LocalStorage

CONVERSATIONS = "/api/v1/conversations"
MESSAGES = "/api/v1/messages"
NOTIFICATIONS = "/api/v1/notifications"

PDF = b"%PDF-1.7\n1 0 obj\n<< /Catalogo >>\nendobj\n%%EOF"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_png(width: int = 40, height: int = 30) -> bytes:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (width, height), (10, 120, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


# --- Conversations --------------------------------------------------------


@pytest.mark.asyncio
async def test_staff_can_open_an_internal_conversation(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = MessagingService(database_session)

    conversation = await service.create_conversation(
        admin_user,
        subject="Estrategia de la demanda",
        conversation_type=ConversationType.INTERNAL,
        case_id=sample_case.id,
    )

    assert conversation.conversation_type == "interna"
    assert conversation.case_id == sample_case.id
    assert conversation.message_count == 0
    assert [p.user_id for p in conversation.participants] == [admin_user.id]


@pytest.mark.asyncio
async def test_a_client_conversation_requires_a_client(
    database_session: AsyncSession, admin_user: User
) -> None:
    service = MessagingService(database_session)

    with pytest.raises(MessageError):
        await service.create_conversation(
            admin_user,
            subject="Conversación sin cliente",
            conversation_type=ConversationType.CLIENT,
        )


@pytest.mark.asyncio
async def test_creator_is_added_as_owner(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    conversation = await MessagingService(database_session).create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id
    )

    participant = conversation.participants[0]

    assert participant.role == "propietario"
    assert participant.last_read_at is None


# --- The internal / portal boundary ---------------------------------------


@pytest.mark.asyncio
async def test_client_user_cannot_be_added_to_an_internal_thread(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    portal_user: tuple[User, Client],
) -> None:
    """Refused, not ignored: silence would look like a successful notification."""
    portal_identity, _client = portal_user
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user, subject="Notas internas", case_id=sample_case.id
    )

    with pytest.raises(MessageError) as excinfo:
        await service.add_participant(
            conversation, portal_identity.id, ConversationType.INTERNAL, admin_user
        )

    assert "interna" in str(excinfo.value)


@pytest.mark.asyncio
async def test_client_cannot_read_an_internal_conversation(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    portal_user: tuple[User, Client],
) -> None:
    portal_identity, _client = portal_user
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user, subject="Notas internas", case_id=sample_case.id
    )
    await service.send_message(conversation, admin_user, "Contenido reservado")

    direct = await service.get_conversation(conversation.id, portal_identity)
    listed = await service.list_conversations(portal_identity)
    messages: list[Message] = []

    assert direct is None
    assert listed == []
    assert messages == []


@pytest.mark.asyncio
async def test_client_sees_only_conversations_about_their_own_client(
    database_session: AsyncSession,
    sample_client: Client,
    sample_case: Case,
    admin_user: User,
    portal_user: tuple[User, Client],
) -> None:
    portal_identity, portal_client = portal_user
    service = MessagingService(database_session)

    mine = await service.create_conversation(
        admin_user,
        subject="Consulta sobre mi expediente",
        conversation_type=ConversationType.CLIENT,
        client_id=portal_client.id,
    )
    await service.add_participant(mine, portal_identity.id, ConversationType.CLIENT, admin_user)

    theirs = await service.create_conversation(
        admin_user,
        subject="Otro cliente",
        conversation_type=ConversationType.CLIENT,
        client_id=sample_client.id,
    )

    listed = await service.list_conversations(portal_identity)

    assert [item.conversation.id for item in listed] == [mine.id]
    assert theirs.id not in {item.conversation.id for item in listed}


@pytest.mark.asyncio
async def test_non_participant_staff_cannot_read_a_conversation(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    staff_user: User,
) -> None:
    """Being an administrator is not a licence to read other people's mail."""
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user, subject="Entre el socio y el pasante", case_id=sample_case.id
    )

    assert await service.get_conversation(conversation.id, staff_user) is None


@pytest.mark.asyncio
async def test_participant_can_read_and_send(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    staff_user: User,
) -> None:
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user,
        subject="Trabajo conjunto",
        case_id=sample_case.id,
        participant_ids=[staff_user.id],
    )

    found = await service.get_conversation(conversation.id, staff_user)
    await service.send_message(conversation, staff_user, "He revisado el contrato")

    assert found is not None
    assert {p.user_id for p in found.participants} == {admin_user.id, staff_user.id}


# --- Messages -------------------------------------------------------------


@pytest.mark.asyncio
async def test_message_updates_the_conversation(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id
    )

    await service.send_message(conversation, admin_user, "Primer mensaje")

    assert conversation.message_count == 1
    assert conversation.last_message_preview == "Primer mensaje"
    assert conversation.last_message_at is not None


@pytest.mark.asyncio
async def test_empty_message_is_refused(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id
    )

    with pytest.raises(MessageError):
        await service.send_message(conversation, admin_user, "   ")


@pytest.mark.asyncio
async def test_oversized_message_is_refused(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id
    )

    with pytest.raises(MessageError):
        await service.send_message(conversation, admin_user, "x" * 5001)


@pytest.mark.asyncio
async def test_non_participant_cannot_send(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    staff_user: User,
) -> None:
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user, subject="Privado", case_id=sample_case.id
    )

    with pytest.raises(MessageError):
        await service.send_message(conversation, staff_user, "Me colé")


@pytest.mark.asyncio
async def test_thread_is_returned_oldest_first(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id
    )
    for index in range(3):
        await service.send_message(conversation, admin_user, f"Mensaje {index}")

    messages = await service.list_messages(conversation.id, admin_user)

    assert [m.body for m in messages] == [
        "Mensaje 0",
        "Mensaje 1",
        "Mensaje 2",
    ]


@pytest.mark.asyncio
async def test_deleted_message_is_hidden_but_keeps_its_slot(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id
    )
    first = await service.send_message(conversation, admin_user, "Me equivoqué")
    await service.send_message(conversation, admin_user, "Correcto")

    await service.delete_message(first, admin_user)
    messages = await service.list_messages(conversation.id, admin_user)

    assert len(messages) == 2
    assert messages[0].deleted_at is not None


# --- Read state -----------------------------------------------------------


@pytest.mark.asyncio
async def test_sender_has_read_their_own_message(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user,
        subject="Hilo",
        case_id=sample_case.id,
        participant_ids=[admin_user.id],
    )

    await service.send_message(conversation, admin_user, "Enviado")

    assert await service.unread_count(conversation.id, None) == 1
    participant = await service.participant(conversation.id, admin_user.id)
    assert participant.last_read_at is not None
    assert await service.unread_count(conversation.id, participant.last_read_at) == 0


@pytest.mark.asyncio
async def test_recipient_sees_it_as_unread(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    staff_user: User,
) -> None:
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id, participant_ids=[staff_user.id]
    )

    await service.send_message(conversation, admin_user, "Revísalo")

    assert await service.total_unread(staff_user) == 1
    assert await service.total_unread(admin_user) == 0

    await service.mark_read(conversation.id, staff_user)

    assert await service.total_unread(staff_user) == 0


@pytest.mark.asyncio
async def test_marking_read_requires_participation(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    staff_user: User,
) -> None:
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id
    )

    with pytest.raises(MessageError):
        await service.mark_read(conversation.id, staff_user)


# --- Attachments ----------------------------------------------------------


@pytest.mark.asyncio
async def test_attachment_is_validated_and_stored(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    message_storage: LocalStorage,
) -> None:
    service = MessagingService(database_session, message_storage)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id
    )
    content = make_png()

    message = await service.send_message(
        conversation,
        admin_user,
        "Miro esta captura",
        attachments=[AttachmentInput("captura.png", content, "image/png")],
    )

    attachments = await service.attachments_of(message.id)
    assert len(attachments) == 1
    assert attachments[0].sha256 == sha256(content).hexdigest()
    assert attachments[0].storage_key.startswith("messages/")
    assert await message_storage.read(attachments[0].storage_key) == content


@pytest.mark.asyncio
async def test_executable_attachment_is_refused(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    message_storage: LocalStorage,
) -> None:
    service = MessagingService(database_session, message_storage)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id
    )

    with pytest.raises(MessageError):
        await service.send_message(
            conversation,
            admin_user,
            "mira esto",
            attachments=[
                AttachmentInput(
                    "disfraz.pdf", b"MZ\x90\x00" + b"\x00" * 32, "application/pdf"
                )
            ],
        )

    assert conversation.message_count == 0


@pytest.mark.asyncio
async def test_too_many_attachments_are_refused(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    message_storage: LocalStorage,
) -> None:
    limit = get_settings().max_attachments_per_message
    service = MessagingService(database_session, message_storage)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id
    )

    with pytest.raises(MessageError):
        await service.send_message(
            conversation,
            admin_user,
            "muchos archivos",
            attachments=[
                AttachmentInput(f"f{index}.png", make_png(), "image/png")
                for index in range(limit + 1)
            ],
        )


@pytest.mark.asyncio
async def test_attachment_download_verifies_the_digest(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    message_storage: LocalStorage,
) -> None:
    service = MessagingService(database_session, message_storage)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id
    )
    message = await service.send_message(
        conversation,
        admin_user,
        "documento",
        attachments=[AttachmentInput("a.pdf", PDF, "application/pdf")],
    )
    attachment = (await service.attachments_of(message.id))[0]

    found, content = await service.read_attachment(message.id, attachment.id, admin_user)

    assert found.id == attachment.id
    assert content == PDF


@pytest.mark.asyncio
async def test_corrupted_attachment_blocks_the_download(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    message_storage: LocalStorage,
) -> None:
    service = MessagingService(database_session, message_storage)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id
    )
    message = await service.send_message(
        conversation,
        admin_user,
        "documento",
        attachments=[AttachmentInput("a.pdf", PDF, "application/pdf")],
    )
    attachment = (await service.attachments_of(message.id))[0]
    await message_storage.write(attachment.storage_key, b"contenido manipulado")

    with pytest.raises(MessageError) as excinfo:
        await service.read_attachment(message.id, attachment.id, admin_user)

    assert "hash" in str(excinfo.value)


@pytest.mark.asyncio
async def test_attachment_of_another_conversation_is_not_readable(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    staff_user: User,
    message_storage: LocalStorage,
) -> None:
    service = MessagingService(database_session, message_storage)
    conversation = await service.create_conversation(
        admin_user, subject="Privado", case_id=sample_case.id
    )
    message = await service.send_message(
        conversation,
        admin_user,
        "privado",
        attachments=[AttachmentInput("a.pdf", PDF, "application/pdf")],
    )
    attachment = (await service.attachments_of(message.id))[0]

    with pytest.raises(MessageError):
        await service.read_attachment(message.id, attachment.id, staff_user)


def test_message_key_never_uses_the_uploaded_name() -> None:
    key = build_message_key(uuid4(), uuid4(), ".pdf")

    assert key.startswith("messages/")
    assert key.endswith(".pdf")


def test_message_key_cleans_the_extension(tmp_path: Path) -> None:
    key = build_message_key(uuid4(), uuid4(), "../../evil")

    assert ".." not in key
    assert key.count("/") == 2


# --- Audit ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_message_audit_never_stores_the_body(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    """The audit table must not become a copy of the firm's correspondence."""
    secret = "Estrategia procesal confidencial con detallekeyboard"
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id
    )

    await service.send_message(conversation, admin_user, secret)

    result = await database_session.execute(
        select(ChangeLog).where(ChangeLog.entity == "messages")
    )
    entries = list(result.scalars().all())
    assert entries, "the send must still be audited"
    for entry in entries:
        assert secret not in (entry.old_value or "")
        assert secret not in (entry.new_value or "")
        assert entry.change_reason is not None


# --- Notifications --------------------------------------------------------


@pytest.mark.asyncio
async def test_participants_are_notified(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    staff_user: User,
) -> None:
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id, participant_ids=[staff_user.id]
    )

    await service.send_message(conversation, admin_user, "Mírame esto")

    notifications = await service.list_notifications(staff_user)
    assert len(notifications) >= 1
    assert any(item.notification_type == "new_message" for item in notifications)
    assert await service.unread_notifications(staff_user) >= 1


@pytest.mark.asyncio
async def test_sender_is_not_notified_of_their_own_message(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    staff_user: User,
) -> None:
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id, participant_ids=[staff_user.id]
    )

    await service.send_message(conversation, admin_user, "Mensaje propio")

    sender_notifications = [
        item
        for item in await service.list_notifications(admin_user)
        if item.notification_type == "new_message"
    ]
    assert sender_notifications == []


@pytest.mark.asyncio
async def test_muted_participant_is_not_notified(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    staff_user: User,
) -> None:
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user, subject="Hilo", case_id=sample_case.id, participant_ids=[staff_user.id]
    )
    participant = await service.participant(conversation.id, staff_user.id)
    participant.is_muted = True
    await database_session.flush()

    await service.send_message(conversation, admin_user, "sin avisar")

    assert [
        item for item in await service.list_notifications(staff_user)
        if item.notification_type == "new_message"
    ] == []


@pytest.mark.asyncio
async def test_notification_can_only_be_read_by_its_owner(
    database_session: AsyncSession, admin_user: User, staff_user: User
) -> None:
    service = MessagingService(database_session)
    notification = await service.notify(
        staff_user, NotificationType.NEW_MESSAGE, title="Privada", body="solo tuya"
    )
    assert notification is not None

    with pytest.raises(MessageError):
        await service.mark_notification_read(notification.id, admin_user)


@pytest.mark.asyncio
async def test_mark_all_read_clears_the_badge(
    database_session: AsyncSession, admin_user: User, staff_user: User
) -> None:
    service = MessagingService(database_session)
    for index in range(3):
        await service.notify(
            staff_user, NotificationType.NEW_MESSAGE, title=f"N{index}", body="x"
        )

    marked = await service.mark_all_notifications_read(staff_user)

    assert marked == 3
    assert await service.unread_notifications(staff_user) == 0


# --- API ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_conversation_and_message_flow(
    client: AsyncClient,
    admin_token: str,
    sample_case: Case,
    message_storage: LocalStorage,
) -> None:
    created = await client.post(
        CONVERSATIONS,
        json={
            "subject": "Hilo de prueba",
            "conversation_type": "interna",
            "case_id": str(sample_case.id),
        },
        headers=_auth(admin_token),
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    sent = await client.post(
        f"{CONVERSATIONS}/{conversation_id}/messages",
        data={"body": "Primer mensaje con adjunto"},
        files={"files": ("captura.png", make_png(), "image/png")},
        headers=_auth(admin_token),
    )
    assert sent.status_code == 201
    assert sent.json()["body"] == "Primer mensaje con adjunto"
    assert len(sent.json()["attachments"]) == 1

    thread = await client.get(
        f"{CONVERSATIONS}/{conversation_id}", headers=_auth(admin_token)
    )
    assert thread.status_code == 200
    assert len(thread.json()["messages"]) == 1
    assert thread.json()["conversation"]["message_count"] == 1


@pytest.mark.asyncio
async def test_api_conversation_of_another_participant_is_404(
    client: AsyncClient, admin_token: str, staff_token: str, sample_case: Case
) -> None:
    created = await client.post(
        CONVERSATIONS,
        json={"subject": "Privada", "conversation_type": "interna"},
        headers=_auth(admin_token),
    )

    response = await client.get(
        f"{CONVERSATIONS}/{created.json()['id']}", headers=_auth(staff_token)
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_api_client_cannot_create_a_conversation(
    client: AsyncClient, portal_token: str, portal_case: Case
) -> None:
    response = await client.post(
        CONVERSATIONS,
        json={"subject": "Quiero hablar", "conversation_type": "cliente"},
        headers=_auth(portal_token),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_api_client_cannot_see_internal_conversations(
    client: AsyncClient,
    admin_token: str,
    portal_token: str,
    sample_case: Case,
) -> None:
    await client.post(
        CONVERSATIONS,
        json={
            "subject": "Notas internas",
            "conversation_type": "interna",
            "case_id": str(sample_case.id),
        },
        headers=_auth(admin_token),
    )

    listed = await client.get(CONVERSATIONS, headers=_auth(portal_token))

    assert listed.status_code == 200
    assert listed.json() == []


@pytest.mark.asyncio
async def test_api_adding_a_client_to_internal_is_refused(
    client: AsyncClient,
    admin_token: str,
    portal_user: tuple[User, Client],
    sample_case: Case,
) -> None:
    portal_identity, _client = portal_user
    created = await client.post(
        CONVERSATIONS,
        json={"subject": "Interna", "conversation_type": "interna"},
        headers=_auth(admin_token),
    )

    response = await client.post(
        f"{CONVERSATIONS}/{created.json()['id']}/participants",
        params={"user_id": str(portal_identity.id)},
        headers=_auth(admin_token),
    )

    assert response.status_code == 409
    assert "interna" in response.json()["error"]["message"]


@pytest.mark.asyncio
async def test_api_client_sees_their_own_thread(
    client: AsyncClient,
    admin_token: str,
    portal_token: str,
    portal_case: Case,
    portal_user: tuple[User, Client],
) -> None:
    portal_identity, portal_client = portal_user
    created = await client.post(
        CONVERSATIONS,
        json={
            "subject": "Consulta del cliente",
            "conversation_type": "cliente",
            "client_id": str(portal_client.id),
            "participant_ids": [str(portal_identity.id)],
        },
        headers=_auth(admin_token),
    )
    assert created.status_code == 201

    listed = await client.get(CONVERSATIONS, headers=_auth(portal_token))
    thread = await client.get(
        f"{CONVERSATIONS}/{created.json()['id']}", headers=_auth(portal_token)
    )

    assert listed.status_code == 200
    assert [item["subject"] for item in listed.json()] == ["Consulta del cliente"]
    assert thread.status_code == 200
    assert portal_case.id is not None


@pytest.mark.asyncio
async def test_client_cannot_join_or_open_another_clients_thread(
    database_session: AsyncSession,
    admin_user: User,
    sample_client: Client,
    portal_user: tuple[User, Client],
) -> None:
    portal_identity, _portal_client = portal_user
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user,
        subject="Correspondencia de otro cliente",
        conversation_type=ConversationType.CLIENT,
        client_id=sample_client.id,
    )

    with pytest.raises(MessageError):
        await service.add_participant(
            conversation,
            portal_identity.id,
            ConversationType.CLIENT,
            admin_user,
        )

    database_session.add(
        ConversationParticipant(
            conversation_id=conversation.id,
            user_id=portal_identity.id,
        )
    )
    await database_session.flush()

    assert await service.get_conversation(conversation.id, portal_identity) is None


@pytest.mark.asyncio
async def test_unassigned_lawyer_cannot_open_thread_on_another_case(
    client: AsyncClient,
    sample_case: Case,
    second_lawyer_token: tuple[object, str],
) -> None:
    _lawyer, token = second_lawyer_token

    response = await client.post(
        CONVERSATIONS,
        json={
            "subject": "Expediente fuera de alcance",
            "conversation_type": "interna",
            "case_id": str(sample_case.id),
        },
        headers=_auth(token),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_case_and_client_must_match_when_opening_thread(
    client: AsyncClient,
    admin_token: str,
    sample_case: Case,
    portal_user: tuple[User, Client],
) -> None:
    _portal_identity, portal_client = portal_user

    response = await client.post(
        CONVERSATIONS,
        json={
            "subject": "Vínculos incompatibles",
            "conversation_type": "cliente",
            "case_id": str(sample_case.id),
            "client_id": str(portal_client.id),
        },
        headers=_auth(admin_token),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_client_without_attach_permission_cannot_upload(
    client: AsyncClient,
    admin_token: str,
    portal_token: str,
    portal_user: tuple[User, Client],
    message_storage: LocalStorage,
) -> None:
    portal_identity, portal_client = portal_user
    created = await client.post(
        CONVERSATIONS,
        json={
            "subject": "Canal sin adjuntos de cliente",
            "conversation_type": "cliente",
            "client_id": str(portal_client.id),
            "participant_ids": [str(portal_identity.id)],
        },
        headers=_auth(admin_token),
    )

    response = await client.post(
        f"{CONVERSATIONS}/{created.json()['id']}/messages",
        data={"body": "Intento de adjunto"},
        files={"files": ("captura.png", make_png(), "image/png")},
        headers=_auth(portal_token),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_thread_contract_includes_participants_and_sender_names(
    client: AsyncClient,
    admin_token: str,
    staff_user: User,
    sample_case: Case,
) -> None:
    created = await client.post(
        CONVERSATIONS,
        json={
            "subject": "Contrato de bandeja",
            "conversation_type": "interna",
            "case_id": str(sample_case.id),
            "participant_ids": [str(staff_user.id)],
        },
        headers=_auth(admin_token),
    )
    await client.post(
        f"{CONVERSATIONS}/{created.json()['id']}/messages",
        data={"body": "Mensaje identificable"},
        headers=_auth(admin_token),
    )

    response = await client.get(
        f"{CONVERSATIONS}/{created.json()['id']}", headers=_auth(admin_token)
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["conversation"]["case_number"] == sample_case.case_number
    assert {item["user_id"] for item in payload["participants"]} >= {
        str(staff_user.id)
    }
    assert payload["messages"][0]["sender_name"]


@pytest.mark.asyncio
async def test_participant_options_never_mix_client_accounts(
    client: AsyncClient,
    admin_token: str,
    portal_user: tuple[User, Client],
    sample_client: Client,
) -> None:
    portal_identity, portal_client = portal_user

    matching = await client.get(
        f"{CONVERSATIONS}/participant-options",
        params={"conversation_type": "cliente", "client_id": str(portal_client.id)},
        headers=_auth(admin_token),
    )
    another = await client.get(
        f"{CONVERSATIONS}/participant-options",
        params={"conversation_type": "cliente", "client_id": str(sample_client.id)},
        headers=_auth(admin_token),
    )

    assert matching.status_code == 200
    assert str(portal_identity.id) in {item["id"] for item in matching.json()}
    assert str(portal_identity.id) not in {item["id"] for item in another.json()}


@pytest.mark.asyncio
async def test_closed_conversation_refuses_new_messages(
    client: AsyncClient,
    admin_token: str,
) -> None:
    created = await client.post(
        CONVERSATIONS,
        json={"subject": "Hilo cerrado", "conversation_type": "interna"},
        headers=_auth(admin_token),
    )
    conversation_id = created.json()["id"]
    closed = await client.patch(
        f"{CONVERSATIONS}/{conversation_id}",
        json={"status": "cerrado"},
        headers=_auth(admin_token),
    )

    response = await client.post(
        f"{CONVERSATIONS}/{conversation_id}/messages",
        data={"body": "No debería entrar"},
        headers=_auth(admin_token),
    )

    assert closed.status_code == 200
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_message_notifies_multiple_recipients(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    staff_user: User,
    plain_user: User,
    rbac_catalog: dict[str, Role],
) -> None:
    second_staff = User(
        email=f"second-staff-{uuid4()}@example.com",
        full_name="Segundo asistente",
        hashed_password=plain_user.hashed_password,
        is_active=True,
        is_verified=True,
    )
    second_staff.roles.append(rbac_catalog["asistente"])
    database_session.add(second_staff)
    await database_session.flush()
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user,
        subject="Equipo completo",
        case_id=sample_case.id,
        participant_ids=[staff_user.id, second_staff.id],
    )

    await service.send_message(conversation, admin_user, "Aviso para ambos")
    result = await database_session.execute(
        select(Notification).where(
            Notification.notification_type == "new_message",
            Notification.user_id.in_([staff_user.id, second_staff.id]),
        )
    )

    assert {item.user_id for item in result.scalars().all()} == {
        staff_user.id,
        second_staff.id,
    }


@pytest.mark.asyncio
async def test_api_unread_summary_reflects_a_new_message(
    client: AsyncClient,
    admin_token: str,
    staff_token: str,
    staff_user: User,
    sample_case: Case,
) -> None:
    """Feeds the dashboards, so it has to be honest about what is pending."""
    before = await client.get(f"{MESSAGES}/unread/summary", headers=_auth(staff_token))
    assert before.json()["unread_messages"] == 0

    created = await client.post(
        CONVERSATIONS,
        json={
            "subject": "Pendiente",
            "conversation_type": "interna",
            "case_id": str(sample_case.id),
            "participant_ids": [str(staff_user.id)],
        },
        headers=_auth(admin_token),
    )
    await client.post(
        f"{CONVERSATIONS}/{created.json()['id']}/messages",
        data={"body": "Revísalo cuando puedas"},
        headers=_auth(admin_token),
    )

    summary = await client.get(f"{MESSAGES}/unread/summary", headers=_auth(staff_token))

    assert summary.status_code == 200
    assert summary.json()["unread_messages"] == 1


@pytest.mark.asyncio
async def test_api_notifications_are_private(
    client: AsyncClient, admin_token: str, staff_token: str
) -> None:
    mine = await client.get(NOTIFICATIONS, headers=_auth(admin_token))
    theirs = await client.get(NOTIFICATIONS, headers=_auth(staff_token))

    assert mine.status_code == 200
    assert theirs.status_code == 200
    assert isinstance(theirs.json(), list)


@pytest.mark.asyncio
async def test_api_requires_authentication(
    client: AsyncClient, sample_case: Case
) -> None:
    listed = await client.get(CONVERSATIONS)
    created = await client.post(CONVERSATIONS, json={"subject": "anonima"})

    assert listed.status_code == 401
    assert created.status_code == 401


@pytest.mark.asyncio
async def test_api_delete_message_requires_permission(
    client: AsyncClient, portal_token: str
) -> None:
    response = await client.delete(
        f"{MESSAGES}/{uuid4()}", headers=_auth(portal_token)
    )

    assert response.status_code == 403


# --- Rate limiting --------------------------------------------------------


def test_messages_have_their_own_rate_limit_profile() -> None:
    from app.middleware.rate_limit import LIMIT_PROFILES, RateLimitMiddleware

    settings = get_settings()
    message_limit = getattr(
        settings, LIMIT_PROFILES["message"][0]
    )
    assert message_limit < settings.rate_limit_requests
    assert message_limit > 0
    assert RateLimitMiddleware is not None


def _starlette_request(path: str, method: str) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "root_path": "",
            "scheme": "http",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
        }
    )


def test_message_rate_limit_applies_only_to_posts() -> None:
    from app.middleware.rate_limit import RateLimitMiddleware

    middleware = RateLimitMiddleware(app=None)

    assert (
        middleware._profile_for(_starlette_request("/api/v1/messages", "POST")) == "message"
    )
    assert (
        middleware._profile_for(_starlette_request("/api/v1/messages", "GET")) == "default"
    )
    assert (
        middleware._profile_for(_starlette_request("/api/v1/auth/login", "POST"))
        == "auth"
    )


# --- adjuntos: acotar antes de leer ------------------------------------------
#
# El limite existia en el service, pero la ruta HTTP leia los ficheros primero y
# solo despues delegaba. El navegador ya habia leido todos los bytes cuando por fin
# recibia el rechazo. Estas cuatro fijan que se rechace con 413 ANTES de leer, y que
# un adjunto valido siga llegando al service.


@pytest.mark.asyncio
async def test_too_many_attachments_are_refused_before_reading(
    client: AsyncClient,
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    admin_token: str,
    message_storage: LocalStorage,
) -> None:
    """La cantidad se comprueba contra el formulario, no despues de leer.

    La comprobacion vive en el endpoint y no en `send_message` a proposito: el
    service no tiene forma de saber si los bytes ya se leyeron de la peticion.
    """
    conversation = await MessagingService(
        database_session, message_storage
    ).create_conversation(admin_user, subject="Hilo", case_id=sample_case.id)

    over = get_settings().max_attachments_per_message + 1
    # The form field is named `files` because that is the parameter name; sending
    # `file` arrives as an empty list, which is how this test first "passed" the
    # endpoint without ever reaching it.
    files = [
        ("files", (f"nota-{index}.txt", b"contenido", "text/plain"))
        for index in range(over)
    ]
    response = await client.post(
        f"{CONVERSATIONS}/{conversation.id}/messages",
        data={"body": "Demasiados adjuntos"},
        files=files,
        headers=_auth(admin_token),
    )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_an_oversized_attachment_is_refused_with_413(
    client: AsyncClient,
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    admin_token: str,
    message_storage: LocalStorage,
) -> None:
    """Se lee `cap + 1` bytes, no el archivo entero.

    `read(cap + 1)` es lo que hace posible la comprobacion: `read()` sin argumento
    devuelve el resto del stream y el limite llega tarde para evitar el coste.
    """
    conversation = await MessagingService(
        database_session, message_storage
    ).create_conversation(admin_user, subject="Hilo", case_id=sample_case.id)
    cap = get_settings().max_attachment_bytes

    response = await client.post(
        f"{CONVERSATIONS}/{conversation.id}/messages",
        data={"body": "Un adjunto enorme"},
        files=[("files", ("grande.txt", b"a" * (cap + 1), "text/plain"))],
        headers=_auth(admin_token),
    )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_attachment_validation_is_serialisable() -> None:
    """`HTTPException` se serializa en JSON sin romperse.

    El detalle de estos rechazos es texto en espanol con el limite en megabytes. Si
    ese texto no fuera str, la respuesta seria un 500 y el cliente veria un error de
    servidor en lugar del 413 que explica el motivo.
    """
    error = HTTPException(
        status_code=HTTP_413_CONTENT_TOO_LARGE, detail="El adjunto es demasiado grande"
    )

    rendered = json.dumps({"detail": error.detail}, ensure_ascii=False)

    assert HTTP_413_CONTENT_TOO_LARGE == 413
    assert "demasiado grande" in rendered


@pytest.mark.asyncio
async def test_a_valid_attachment_reaches_the_service(
    client: AsyncClient,
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    admin_token: str,
    message_storage: LocalStorage,
) -> None:
    """The counterpart: bounding the request must not break the happy path.

    Sin esta, una prueba que envíe el campo con el nombre equivocado deja todo el
    camino de adjuntos sin ejercitar y aun así se ve verde.
    """
    conversation = await MessagingService(
        database_session, message_storage
    ).create_conversation(admin_user, subject="Hilo", case_id=sample_case.id)

    response = await client.post(
        f"{CONVERSATIONS}/{conversation.id}/messages",
        data={"body": "Adjunto válido"},
        files=[("files", ("nota.txt", b"contenido de la nota", "text/plain"))],
        headers=_auth(admin_token),
    )

    assert response.status_code == 201
    assert len(response.json()["attachments"]) == 1

# --- alcance de expediente ---------------------------------------------------
#
# create_conversation resolvió el alcance al escribir, pero nada lo volvió a
# comprobar al leer. La participación era la única puerta: un abogado que estuvo
# en un hilo y luego salió del expediente seguía leyéndolo, con su case_number,
# y podía descargar los adjuntos. Estar en la conversación responde "me
# escribieron esto"; no responde "puedo seguir viéndolo".


@pytest.mark.asyncio
async def test_a_participant_who_lost_the_case_stops_seeing_the_thread(
    client: AsyncClient,
    database_session: AsyncSession,
    admin_user: User,
    other_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    lawyer, token = second_lawyer_token
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user,
        subject="Estrategia de la prueba",
        conversation_type=ConversationType.INTERNAL,
        case_id=other_case.id,
        participant_ids=[cast(UUID, lawyer.user_id)],
    )
    await service.send_message(conversation, admin_user, "Ultimas novedades.")

    detail = await client.get(
        f"{CONVERSATIONS}/{conversation.id}", headers=_auth(token)
    )

    assert detail.status_code == 404


@pytest.mark.asyncio
async def test_that_thread_leaves_the_listing(
    client: AsyncClient,
    database_session: AsyncSession,
    admin_user: User,
    other_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """A restricted list that still leaks rows is a leak with extra steps."""
    lawyer, token = second_lawyer_token
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user,
        subject="Estrategia de la prueba",
        conversation_type=ConversationType.INTERNAL,
        case_id=other_case.id,
        participant_ids=[cast(UUID, lawyer.user_id)],
    )

    listed = await client.get(CONVERSATIONS, headers=_auth(token))

    assert listed.status_code == 200
    assert conversation.id not in {item["id"] for item in listed.json()}


@pytest.mark.asyncio
async def test_its_messages_and_attachments_stop_being_readable(
    client: AsyncClient,
    database_session: AsyncSession,
    admin_user: User,
    admin_token: str,
    other_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
    message_storage: LocalStorage,
) -> None:
    """The bytes are the point of the leak, so they are what the test checks."""
    lawyer, token = second_lawyer_token
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user,
        subject="Estrategia de la prueba",
        conversation_type=ConversationType.INTERNAL,
        case_id=other_case.id,
        participant_ids=[cast(UUID, lawyer.user_id)],
    )
    sent = await client.post(
        f"{CONVERSATIONS}/{conversation.id}/messages",
        data={"body": "Adjunto el strategy."},
        files=[("files", ("strategy.txt", b"contenido reservado", "text/plain"))],
        headers=_auth(admin_token),
    )
    assert sent.status_code == 201

    message = await client.get(f"{MESSAGES}/{sent.json()['id']}", headers=_auth(token))
    assert message.status_code == 404

    attachment_id = sent.json()["attachments"][0]["id"]
    download = await client.get(
        f"{MESSAGES}/attachments/{attachment_id}", headers=_auth(token)
    )
    assert download.status_code == 404


@pytest.mark.asyncio
async def test_a_thread_on_your_own_case_still_works(
    client: AsyncClient,
    database_session: AsyncSession,
    admin_user: User,
    sample_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """The counterpart: once reads are filtered, the risk is the filter being too tight."""
    lawyer, token = second_lawyer_token
    database_session.add(
        CaseLawyer(
            case_id=sample_case.id,
            lawyer_id=lawyer.id,
            role="titular",
            assigned_at=datetime.now(UTC),
        )
    )
    await database_session.flush()
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user,
        subject="Mi expediente",
        conversation_type=ConversationType.INTERNAL,
        case_id=sample_case.id,
        participant_ids=[cast(UUID, lawyer.user_id)],
    )
    await service.send_message(conversation, admin_user, "Todo en orden.")

    response = await client.get(
        f"{CONVERSATIONS}/{conversation.id}", headers=_auth(token)
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_a_thread_without_a_case_stays_readable(
    client: AsyncClient,
    database_session: AsyncSession,
    admin_user: User,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """A case-less thread is firm material and keeps working.

    Pinned because the fix must not become a global restriction: internal notes
    with no expediente attached are ordinary practice.
    """
    lawyer, token = second_lawyer_token
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user,
        subject="Nota interna sin expediente",
        conversation_type=ConversationType.INTERNAL,
        participant_ids=[cast(UUID, lawyer.user_id)],
    )

    response = await client.get(
        f"{CONVERSATIONS}/{conversation.id}", headers=_auth(token)
    )

    assert response.status_code == 200

@pytest.mark.asyncio
async def test_a_participant_who_lost_the_case_cannot_mutate_the_thread(
    client: AsyncClient,
    database_session: AsyncSession,
    admin_user: User,
    other_case: Case,
    staff_user: User,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """Scope applies to writes too: membership alone must not grant control."""
    lawyer, token = second_lawyer_token
    service = MessagingService(database_session)
    conversation = await service.create_conversation(
        admin_user,
        subject="Estrategia",
        conversation_type=ConversationType.INTERNAL,
        case_id=other_case.id,
        participant_ids=[cast(UUID, lawyer.user_id)],
    )

    update = await client.patch(
        f"{CONVERSATIONS}/{conversation.id}",
        json={"status": "cerrado"},
        headers=_auth(token),
    )
    add = await client.post(
        f"{CONVERSATIONS}/{conversation.id}/participants",
        params={"user_id": str(staff_user.id)},
        headers=_auth(token),
    )
    lawyer_user = await database_session.get(User, lawyer.user_id)
    assert lawyer_user is not None
    own = await service.send_message(conversation, lawyer_user, "mio")
    delete = await client.delete(
        f"{MESSAGES}/{own.id}",
        headers=_auth(token),
    )

    assert update.status_code == 404
    assert add.status_code == 404
    assert delete.status_code == 404
