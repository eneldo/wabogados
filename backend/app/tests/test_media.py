"""The multimedia library (MASTER_PROMPT V4).

Two things are worth stating before the tests, because they are the decisions that
made the module safe to write at all:

1. **It is not the evidence engine.** Nothing here touches `EVIDENCE_MIME_TYPES`,
   the immutable original or the custody chain. A recording that belongs to a case
   is evidence; a copy filed here is working material.
2. **The kind follows the bytes.** The browser is free to send whatever it likes,
   and there is a test that proves an MP4 announced as an image is filed as a video.
"""

from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Case, CaseLawyer, ChangeLog, Lawyer, MediaAccessLog, User
from app.schemas.media import MediaCreate
from app.services.media import (
    MEDIA_ENTITY,
    MediaError,
    MediaService,
    MediaValidationError,
    detect_media_type,
    kind_for,
)
from app.services.storage_local import LocalStorage

MEDIA = "/api/v1/media"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Header detection -----------------------------------------------------


def _mp4(payload: bytes = b"video-bytes") -> bytes:
    """A minimal ISO base media header: a box size then the `ftyp` brand."""
    return b"\x00\x00\x00\x18ftypisom" + b"\x00\x00\x00\x00isom" + payload


def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"ihdr" + b"0" * 32


def _webm() -> bytes:
    return b"\x1a\x45\xdf\xa3" + b"webm" * 4


def _mp3() -> bytes:
    return b"ID3\x03\x00\x00\x00" + b"audio" * 8


def test_the_kind_follows_the_bytes_not_the_browser() -> None:
    assert detect_media_type(_mp4()) == "video/mp4"
    assert detect_media_type(_webm()) == "video/webm"
    assert detect_media_type(_png()) == "image/png"
    assert detect_media_type(_mp3()) == "audio/mpeg"
    assert detect_media_type(b"%PDF-1.7 rest") == "application/pdf"


def test_an_unknown_header_is_refused_rather_than_guessed() -> None:
    """A file whose type cannot be read is not one the library stores."""
    assert detect_media_type(b"MZ\x90\x00 this is a windows binary") is None
    assert detect_media_type(b"") is None


def test_riff_is_resolved_by_its_form_type() -> None:
    """`RIFF` alone is a container, not a format.

    Taking it for audio would file every `.webp` as sound, and taking it for
    anything else would refuse every wav.
    """
    assert detect_media_type(b"RIFF\x24\x00\x00\x00WAVEfmt ") == "audio/wav"
    assert detect_media_type(b"RIFF\x24\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert detect_media_type(b"RIFF\x24\x00\x00\x00XXXXnope") is None


def test_an_mp4_brand_of_audio_is_filed_as_audio() -> None:
    assert detect_media_type(b"\x00\x00\x00\x18ftypM4A " + b"\x00" * 8) == "audio/mp4"


def test_kind_is_derived_from_the_detected_type() -> None:
    assert kind_for("video/mp4") == "video"
    assert kind_for("image/png") == "image"
    with pytest.raises(MediaValidationError):
        kind_for("application/x-dosexec")


# --- Service --------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_row_can_be_registered_before_the_file_arrives(
    database_session: AsyncSession, admin_user: User
) -> None:
    """A librarian files a recording that has not been uploaded yet.

    The screen has to tell those two states apart, which is what `has_file` is for.
    """
    item = await MediaService(database_session).create(
        MediaCreate(title="Inspección obra norte", description="Sin archivo todavía"),
        admin_user,
    )

    assert item.has_file is False
    assert item.mime_type is None
    assert item.is_active is True
    assert item.kind == "document"


@pytest.mark.asyncio
async def test_attaching_a_file_records_the_digest_of_what_was_stored(
    database_session: AsyncSession, admin_user: User, media_storage: LocalStorage
) -> None:
    import hashlib

    service = MediaService(database_session)
    item = await service.create(MediaCreate(title="Declaración en video"), admin_user)

    updated = await service.attach_file(item, _mp4(), "video-final.mp4")

    assert updated.has_file is True
    assert updated.kind == "video"
    assert updated.mime_type == "video/mp4"
    # The digest kept is the one the backend computed for the stored object, which
    # is the only one that can later prove the bytes were not altered (ADR-041).
    assert updated.sha256 == hashlib.sha256(_mp4()).hexdigest()
    assert updated.size_bytes == len(_mp4())
    assert updated.original_filename == "video-final.mp4"


@pytest.mark.asyncio
async def test_a_binary_the_library_does_not_accept_is_refused(
    database_session: AsyncSession, admin_user: User, media_storage: LocalStorage
) -> None:
    """Video is accepted; an executable is not, whatever it calls itself."""
    service = MediaService(database_session)
    item = await service.create(MediaCreate(title="Binario"), admin_user)

    with pytest.raises(MediaValidationError):
        await service.attach_file(item, b"MZ\x90\x00 not a video", "video.mp4")


@pytest.mark.asyncio
async def test_replacing_the_file_leaves_one_object_per_record(
    database_session: AsyncSession, admin_user: User, media_storage: LocalStorage
) -> None:
    service = MediaService(database_session)
    item = await service.create(MediaCreate(title="Grabación"), admin_user)
    first = await service.attach_file(item, _mp4(b"primera"), "a.mp4")
    first_key = first.storage_key
    assert first_key is not None

    second = await service.attach_file(first, _mp4(b"segunda"), "b.mp4")
    second_key = second.storage_key
    assert second_key is not None

    assert second_key != first_key
    assert not await media_storage.exists(first_key)
    assert await media_storage.exists(second_key)
    assert second.size_bytes == len(_mp4(b"segunda"))


@pytest.mark.asyncio
async def test_deactivating_keeps_the_row_the_history_and_the_file(
    database_session: AsyncSession, admin_user: User, media_storage: LocalStorage
) -> None:
    """ADR-051: nothing is deleted, and a deactivated row stays readable.

    The file in particular: a row that lost its bytes could not be brought back,
    which is the whole reason rows are deactivated instead of removed.
    """
    service = MediaService(database_session)
    item = await service.create(MediaCreate(title="Acta notarial"), admin_user)
    item = await service.attach_file(item, _mp4(), "acta.mp4")
    key = item.storage_key
    assert key is not None

    deactivated = await service.deactivate(item, admin_user)

    assert deactivated.is_active is False
    assert deactivated.deleted_at is not None
    assert deactivated.deleted_by == admin_user.id
    assert await media_storage.exists(key)

    back = await service.reactivate(deactivated, admin_user)
    assert back.is_active is True
    assert back.deleted_at is None


@pytest.mark.asyncio
async def test_the_history_records_the_digest_of_a_replaced_file(
    database_session: AsyncSession, admin_user: User, media_storage: LocalStorage
) -> None:
    service = MediaService(database_session)
    item = await service.create(MediaCreate(title="Audiencia 1"), admin_user)
    await service.attach_file(item, _mp4(b"antes"), "a.mp4")
    await service.attach_file(item, _mp4(b"despues"), "b.mp4")

    result = await database_session.execute(
        select(ChangeLog)
        .where(ChangeLog.entity == MEDIA_ENTITY, ChangeLog.entity_id == item.id)
        .order_by(ChangeLog.created_at)
    )
    entries = {(row.field_name, row.new_value) for row in result.scalars()}

    # Two digests, and a reason: months later this is what answers "which file
    # was in the library that day".
    digests = {value for field, value in entries if field == "sha256"}
    assert len(digests) == 2


@pytest.mark.asyncio
async def test_a_file_without_one_cannot_be_read(
    database_session: AsyncSession, admin_user: User, media_storage: LocalStorage
) -> None:
    service = MediaService(database_session)
    item = await service.create(MediaCreate(title="Vacío"), admin_user)

    with pytest.raises(MediaError):
        await service.read_file(item)


# --- Listing --------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_listing_filters_by_text_kind_and_state(
    database_session: AsyncSession, admin_user: User, media_storage: LocalStorage
) -> None:
    service = MediaService(database_session)
    video = await service.create(
        MediaCreate(title="Inspección puente", tags="obra, puente"), admin_user
    )
    await service.attach_file(video, _mp4(), "p.mp4")
    photo = await service.create(
        MediaCreate(title="Fachada", confidentiality="restringido"), admin_user
    )
    await service.attach_file(photo, _png(), "f.png")
    hidden = await service.create(MediaCreate(title="Borrador"), admin_user)
    await service.deactivate(hidden, admin_user)

    items, total = await service.list_media(scope_clause=None, search="obra")
    assert total == 1
    assert items[0].id == video.id

    by_tag, tagged_total = await service.list_media(scope_clause=None, search="puente")
    assert tagged_total == 1
    assert by_tag[0].id == video.id

    videos, video_total = await service.list_media(scope_clause=None, kind="video")
    assert video_total == 1
    assert videos[0].id == video.id

    restricted, restricted_total = await service.list_media(
        scope_clause=None, confidentiality="restringido"
    )
    assert restricted_total == 1
    assert restricted[0].id == photo.id

    # A deactivated row leaves the default listing and only returns when asked for.
    assert len(await service.list_media(scope_clause=None)) == 2
    everything, all_total = await service.list_media(scope_clause=None, include_inactive=True)
    assert all_total == 3
    assert len(everything) == 3


# --- API ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_library_is_invisible_to_a_client(
    client: AsyncClient, portal_token: str
) -> None:
    """The library is firm material; nothing in it is published to the portal."""
    assert (await client.get(MEDIA, headers=_auth(portal_token))).status_code == 403
    assert (await client.get(MEDIA)).status_code == 401


@pytest.mark.asyncio
async def test_a_staff_profile_works_the_library_but_cannot_deactivate(
    client: AsyncClient,
    database_session: AsyncSession,
    staff_user: User,
    staff_token: str,
    media_storage: LocalStorage,
) -> None:
    """The one `:delete` of the module belongs to the administrator alone.

    Read, create, upload and download are the daily work of a lawyer and an
    assistant; taking a row out of the library is not, and the API refuses it even
    though the screen will not offer the button.
    """
    assert (await client.get(MEDIA, headers=_auth(staff_token))).status_code == 200

    created = await client.post(
        MEDIA,
        json={"title": "Grabación del abogado"},
        headers=_auth(staff_token),
    )
    assert created.status_code == 201
    media_id = created.json()["id"]

    uploaded = await client.put(
        f"{MEDIA}/{media_id}/content",
        files={"file": ("g.mp4", BytesIO(_mp4()), "video/mp4")},
        headers=_auth(staff_token),
    )
    assert uploaded.status_code == 200
    assert (
        await client.get(f"{MEDIA}/{media_id}/content", headers=_auth(staff_token))
    ).status_code == 200

    refused = await client.delete(f"{MEDIA}/{media_id}", headers=_auth(staff_token))
    assert refused.status_code == 403
    assert refused.json()["error"]["message"] == "Permiso requerido: media:delete"

    # And the refusal did not touch the row.
    still = await MediaService(database_session).get(media_id, scope_clause=None)
    assert still is not None
    assert still.is_active is True


@pytest.mark.asyncio
async def test_register_upload_and_read_back(
    client: AsyncClient, admin_token: str, media_storage: LocalStorage
) -> None:
    created = await client.post(
        MEDIA,
        json={"title": "Inspección vía pública", "tags": "obra, vía"},
        headers=_auth(admin_token),
    )
    assert created.status_code == 201
    payload = created.json()
    assert payload["has_file"] is False
    media_id = payload["id"]

    uploaded = await client.put(
        f"{MEDIA}/{media_id}/content",
        files={"file": ("inspeccion.mp4", BytesIO(_mp4()), "video/mp4")},
        headers=_auth(admin_token),
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["kind"] == "video"
    assert uploaded.json()["has_file"] is True

    read = await client.get(f"{MEDIA}/{media_id}", headers=_auth(admin_token))
    assert read.json()["mime_type"] == "video/mp4"

    listed = await client.get(MEDIA, headers=_auth(admin_token))
    assert listed.json()["total"] == 1


@pytest.mark.asyncio
async def test_an_mp4_announced_as_an_image_is_still_a_video(
    client: AsyncClient, admin_token: str, media_storage: LocalStorage
) -> None:
    """The declared type is ignored; the bytes decide.

    A browser sends `Content-Type` from the file extension, so an MP4 renamed to
    `.jpg` arrives claiming to be an image. If the server believed it, the library
    would offer a broken `<img>` for a video.
    """
    created = await client.post(
        MEDIA, json={"title": "Renombrado"}, headers=_auth(admin_token)
    )
    media_id = created.json()["id"]

    uploaded = await client.put(
        f"{MEDIA}/{media_id}/content",
        files={"file": ("mentira.jpg", BytesIO(_mp4()), "image/jpeg")},
        headers=_auth(admin_token),
    )

    assert uploaded.status_code == 200
    assert uploaded.json()["kind"] == "video"
    assert uploaded.json()["mime_type"] == "video/mp4"


@pytest.mark.asyncio
async def test_downloading_an_empty_resource_is_a_conflict_not_a_crash(
    client: AsyncClient, admin_token: str, media_storage: LocalStorage
) -> None:
    created = await client.post(
        MEDIA, json={"title": "Todavía sin archivo"}, headers=_auth(admin_token)
    )
    media_id = created.json()["id"]

    response = await client.get(f"{MEDIA}/{media_id}/content", headers=_auth(admin_token))

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_a_video_is_served_inline_and_in_parts(
    client: AsyncClient, admin_token: str, media_storage: LocalStorage
) -> None:
    """`Range` is what makes a video scrubbable.

    A player asking for the middle of the file and receiving the whole thing, or a
    200 with no `Accept-Ranges`, is a video that cannot be seeked — which on a
    twenty-minute deposition is the difference between usable and not.
    """
    payload = _mp4(b"contenido-lo-suficientemente-largo")
    created = await client.post(
        MEDIA, json={"title": "Deposition"}, headers=_auth(admin_token)
    )
    media_id = created.json()["id"]
    await client.put(
        f"{MEDIA}/{media_id}/content",
        files={"file": ("d.mp4", BytesIO(payload), "video/mp4")},
        headers=_auth(admin_token),
    )

    whole = await client.get(f"{MEDIA}/{media_id}/content", headers=_auth(admin_token))
    assert whole.status_code == 200
    assert whole.headers["accept-ranges"] == "bytes"
    assert whole.headers["content-type"] == "video/mp4"
    # Inline, because a library whose files can only be downloaded cannot be watched.
    assert whole.headers["content-disposition"].startswith("inline")
    assert whole.headers["x-content-type-options"] == "nosniff"

    part = await client.get(
        f"{MEDIA}/{media_id}/content",
        headers={**_auth(admin_token), "Range": "bytes=10-19"},
    )
    assert part.status_code == 206
    assert part.content == payload[10:20]
    assert part.headers["content-range"] == f"bytes 10-19/{len(payload)}"

    open_ended = await client.get(
        f"{MEDIA}/{media_id}/content",
        headers={**_auth(admin_token), "Range": "bytes=20-"},
    )
    assert open_ended.status_code == 206
    assert open_ended.content == payload[20:]

    suffix = await client.get(
        f"{MEDIA}/{media_id}/content",
        headers={**_auth(admin_token), "Range": "bytes=-5"},
    )
    assert suffix.status_code == 206
    assert suffix.content == payload[-5:]


@pytest.mark.asyncio
async def test_a_range_past_the_end_is_refused_rather_than_silently_whole(
    client: AsyncClient, admin_token: str, media_storage: LocalStorage
) -> None:
    """A player that jumped past the end must be told the file is shorter."""
    created = await client.post(
        MEDIA, json={"title": "Corto"}, headers=_auth(admin_token)
    )
    media_id = created.json()["id"]
    await client.put(
        f"{MEDIA}/{media_id}/content",
        files={"file": ("c.mp4", BytesIO(_mp4(b"corto")), "video/mp4")},
        headers=_auth(admin_token),
    )

    response = await client.get(
        f"{MEDIA}/{media_id}/content",
        headers={**_auth(admin_token), "Range": "bytes=999999-"},
    )

    assert response.status_code == 416


@pytest.mark.asyncio
async def test_deactivating_and_reactivating_keeps_the_file(
    client: AsyncClient, admin_token: str, media_storage: LocalStorage
) -> None:
    created = await client.post(
        MEDIA, json={"title": "Se archiva"}, headers=_auth(admin_token)
    )
    media_id = created.json()["id"]
    await client.put(
        f"{MEDIA}/{media_id}/content",
        files={"file": ("a.mp4", BytesIO(_mp4()), "video/mp4")},
        headers=_auth(admin_token),
    )

    deactivated = await client.delete(f"{MEDIA}/{media_id}", headers=_auth(admin_token))
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    # Gone from the default listing, present when asked for.
    assert (await client.get(MEDIA, headers=_auth(admin_token))).json()["total"] == 0
    assert (
        await client.get(
            f"{MEDIA}?include_inactive=true", headers=_auth(admin_token)
        )
    ).json()["total"] == 1

    # And the bytes are still there, so bringing it back is a real restoration.
    back = await client.post(f"{MEDIA}/{media_id}/reactivate", headers=_auth(admin_token))
    assert back.status_code == 200
    assert back.json()["has_file"] is True
    assert (
        await client.get(f"{MEDIA}/{media_id}/content", headers=_auth(admin_token))
    ).status_code == 200


@pytest.mark.asyncio
async def test_the_history_is_readable(
    client: AsyncClient, admin_token: str, media_storage: LocalStorage
) -> None:
    created = await client.post(
        MEDIA, json={"title": "Con historia"}, headers=_auth(admin_token)
    )
    media_id = created.json()["id"]
    await client.put(
        f"{MEDIA}/{media_id}/content",
        files={"file": ("h.mp4", BytesIO(_mp4()), "video/mp4")},
        headers=_auth(admin_token),
    )
    await client.patch(
        f"{MEDIA}/{media_id}",
        json={"title": "Con historia corregida"},
        headers=_auth(admin_token),
    )

    history = await client.get(f"{MEDIA}/{media_id}/history", headers=_auth(admin_token))

    assert history.status_code == 200
    fields = {entry["field_name"] for entry in history.json()}
    assert "title" in fields
    assert "sha256" in fields


@pytest.mark.asyncio
async def test_an_unknown_resource_is_a_404(
    client: AsyncClient, admin_token: str
) -> None:
    missing = uuid4()
    assert (
        await client.get(f"{MEDIA}/{missing}", headers=_auth(admin_token))
    ).status_code == 404
    assert (
        await client.get(f"{MEDIA}/{missing}/content", headers=_auth(admin_token))
    ).status_code == 404


@pytest.mark.asyncio
async def test_listing_refuses_a_page_past_the_end(
    client: AsyncClient, admin_token: str
) -> None:
    """The 422 pattern of every other listing in the project."""
    response = await client.get(f"{MEDIA}?limit=500", headers=_auth(admin_token))

    assert response.status_code == 422


# --- rastro de descarga ----------------------------------------------------


@pytest.mark.asyncio
async def test_every_download_is_recorded(
    client: AsyncClient,
    database_session: AsyncSession,
    staff_token: str,
    staff_user: User,
    media_storage: LocalStorage,
) -> None:
    """A media download wrote nothing anywhere.

    The audit middleware records mutations, so serving bytes produced no row at all,
    while the evidence chain of custody recorded every read. The library holds
    recordings and signature images, so "who opened this file and from where" is a
    question the firm will eventually have to answer.
    """
    created = await client.post(
        MEDIA, json={"title": "Grabacion"}, headers=_auth(staff_token)
    )
    media_id = created.json()["id"]
    await client.put(
        f"{MEDIA}/{media_id}/content",
        files={"file": ("g.mp4", BytesIO(_mp4()), "video/mp4")},
        headers=_auth(staff_token),
    )

    response = await client.get(
        f"{MEDIA}/{media_id}/content",
        headers={**_auth(staff_token), "User-Agent": "pytest/1"},
    )
    assert response.status_code == 200

    rows = (
        await database_session.execute(
            select(MediaAccessLog).where(MediaAccessLog.media_id == UUID(media_id))
        )
    ).scalars().all()

    assert len(rows) == 1
    assert rows[0].access_type == "download"
    assert rows[0].user_id == staff_user.id
    assert rows[0].bytes_served == len(_mp4())
    assert rows[0].user_agent == "pytest/1"


@pytest.mark.asyncio
async def test_a_ranged_read_records_only_what_it_served(
    client: AsyncClient,
    database_session: AsyncSession,
    staff_token: str,
    media_storage: LocalStorage,
) -> None:
    """A video player seeks, and each seek is a request.

    Recording the stored size on every partial read would make the trail say the whole
    file left the server once per scrub, which is both wrong and exactly the kind of
    wrong that makes an audit column untrustworthy.
    """
    created = await client.post(
        MEDIA, json={"title": "Grabacion larga"}, headers=_auth(staff_token)
    )
    media_id = created.json()["id"]
    await client.put(
        f"{MEDIA}/{media_id}/content",
        files={"file": ("g.mp4", BytesIO(_mp4(b"0123456789")), "video/mp4")},
        headers=_auth(staff_token),
    )

    response = await client.get(
        f"{MEDIA}/{media_id}/content",
        headers={**_auth(staff_token), "Range": "bytes=0-3"},
    )
    assert response.status_code == 206

    row = (
        await database_session.execute(
            select(MediaAccessLog).where(MediaAccessLog.media_id == UUID(media_id))
        )
    ).scalar_one()

    assert row.bytes_served == 4


# --- alcance ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_media_of_an_unassigned_case_cannot_be_downloaded(
    client: AsyncClient,
    admin_token: str,
    second_lawyer_token: tuple[Lawyer, str],
    other_case: Case,
    media_storage: LocalStorage,
) -> None:
    """`media:download` said *what*, never *which*, and this route served anything.

    The whole media router took no `get_user_scope`. A lawyer with no assignments
    could list the whole library, open any resource, replace its file, download the
    bytes and read its history. `media_items.case_id` exists and is populated, so the
    expediente was there to filter on and simply was not used.
    """
    _, stranger = second_lawyer_token
    created = await client.post(
        MEDIA,
        json={"title": "Inspeccion", "case_id": str(other_case.id)},
        headers=_auth(admin_token),
    )
    media_id = created.json()["id"]
    await client.put(
        f"{MEDIA}/{media_id}/content",
        files={"file": ("g.mp4", BytesIO(_mp4()), "video/mp4")},
        headers=_auth(admin_token),
    )

    response = await client.get(
        f"{MEDIA}/{media_id}/content", headers=_auth(stranger)
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_media_of_an_unassigned_case_is_not_readable(
    client: AsyncClient,
    admin_token: str,
    other_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    _, stranger = second_lawyer_token
    created = await client.post(
        MEDIA,
        json={"title": "Inspeccion", "case_id": str(other_case.id)},
        headers=_auth(admin_token),
    )

    response = await client.get(f"{MEDIA}/{created.json()['id']}", headers=_auth(stranger))

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_unassigned_media_stays_out_of_the_listing(
    client: AsyncClient,
    admin_token: str,
    other_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    _, stranger = second_lawyer_token
    created = await client.post(
        MEDIA,
        json={"title": "Inspeccion", "case_id": str(other_case.id)},
        headers=_auth(admin_token),
    )
    media_id = created.json()["id"]

    response = await client.get(MEDIA, headers=_auth(stranger))

    assert response.status_code == 200
    assert media_id not in {item["id"] for item in response.json()["items"]}


@pytest.mark.asyncio
async def test_media_of_your_own_case_is_readable(
    client: AsyncClient,
    database_session: AsyncSession,
    admin_token: str,
    sample_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """The counterpart: a scope filter with no hole breaks the firm's own work."""
    second_lawyer, token = second_lawyer_token
    database_session.add(
        CaseLawyer(
            case_id=sample_case.id,
            lawyer_id=second_lawyer.id,
            role="titular",
            assigned_at=datetime.now(UTC),
        )
    )
    await database_session.flush()
    created = await client.post(
        MEDIA,
        json={"title": "Inspeccion propia", "case_id": str(sample_case.id)},
        headers=_auth(admin_token),
    )

    response = await client.get(f"{MEDIA}/{created.json()['id']}", headers=_auth(token))

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_firm_material_stays_visible_to_everybody_with_the_permission(
    client: AsyncClient,
    admin_token: str,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """A resource with no `case_id` is firm material and stays reachable.

    Pinned for the same reason as the invoice one: the library is mostly templates
    and firm-wide recordings, so hiding them would be wrong, and tightening that later
    should be a decision rather than a side effect.
    """
    _, stranger = second_lawyer_token
    created = await client.post(
        MEDIA, json={"title": "Plantilla de informe"}, headers=_auth(admin_token)
    )

    response = await client.get(f"{MEDIA}/{created.json()['id']}", headers=_auth(stranger))

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_media_cannot_be_published_to_a_foreign_case(
    client: AsyncClient,
    sample_case: Case,
    other_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """Writes need the scope too.

    Otherwise a restricted caller files the firm's internal material into somebody
    else's expediente and receives a row they can no longer open.
    """
    _, token = second_lawyer_token

    response = await client.post(
        MEDIA,
        json={"title": "Inspeccion ajena", "case_id": str(other_case.id)},
        headers=_auth(token),
    )

    assert response.status_code == 403
