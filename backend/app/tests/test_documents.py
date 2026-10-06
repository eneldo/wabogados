"""Document tests: validation by content, immutable versions and audited downloads."""

from datetime import date
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Case, Client, Document, DocumentDownload, User
from app.schemas.documents import DocumentCreate
from app.services.documents import DocumentError, DocumentService
from app.services.storage import StorageError, StorageTier
from app.services.storage_local import LocalStorage
from app.services.uploads import (
    MAX_UPLOAD_BYTES,
    UploadValidationError,
    detect_mime_type,
    validate_upload,
)

DOCUMENTS = "/api/v1/documents"

PDF_BYTES = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
EXE_BYTES = b"MZ\x90\x00" + b"\x00" * 32


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _document(case_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "case_id": case_id,
        "document_type": "contrato",
        "title": "Contrato de servicios",
        "description": "Documento firmado por ambas partes",
    }
    payload.update(overrides)
    return payload


# --- Upload validation -------------------------------------------------


def test_detects_mime_from_content_not_extension() -> None:
    assert detect_mime_type(PDF_BYTES) == "application/pdf"
    assert detect_mime_type(PNG_BYTES) == "image/png"
    assert detect_mime_type(b"contenido que no es una imagen") is None


def test_executable_content_is_rejected() -> None:
    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(EXE_BYTES, "contrato.pdf")

    assert "no permitido" in str(excinfo.value)


def test_renamed_executable_is_rejected_despite_pdf_extension() -> None:
    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(EXE_BYTES, "demanda.pdf", "application/pdf")

    assert "no permitido" in str(excinfo.value)


def test_extension_mismatch_is_rejected() -> None:
    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(PNG_BYTES, "contrato.pdf")

    assert "no coincide" in str(excinfo.value)


def test_declared_type_mismatch_is_rejected() -> None:
    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(PDF_BYTES, "contrato.pdf", "image/png")

    assert "declarado" in str(excinfo.value)


def test_empty_upload_is_rejected() -> None:
    with pytest.raises(UploadValidationError):
        validate_upload(b"", "vacio.pdf")


def test_oversized_upload_is_rejected() -> None:
    oversized = b"%PDF-" + b"0" * (MAX_UPLOAD_BYTES + 10)

    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(oversized, "grande.pdf")

    assert "supera el máximo" in str(excinfo.value)


def test_valid_upload_reports_detected_facts() -> None:
    validated = validate_upload(PDF_BYTES, "contrato.pdf", "application/pdf")

    assert validated.mime_type == "application/pdf"
    assert validated.size_bytes == len(PDF_BYTES)
    assert validated.sha256 == sha256(PDF_BYTES).hexdigest()
    assert validated.extension == ".pdf"


def test_text_upload_is_accepted() -> None:
    validated = validate_upload(b"acta notarial en texto plano", "acta.txt")

    assert validated.mime_type == "text/plain"


def test_script_shebang_is_rejected() -> None:
    with pytest.raises(UploadValidationError) as excinfo:
        validate_upload(b"#!/bin/sh\nrm -rf /\n", "notas.txt")

    assert "no permitido" in str(excinfo.value)


def test_prose_starting_with_from_is_not_treated_as_executable() -> None:
    validated = validate_upload(
        b"from the analysis of the case it follows that...", "informe.txt"
    )

    assert validated.mime_type == "text/plain"


def test_elf_binary_is_rejected() -> None:
    with pytest.raises(UploadValidationError):
        validate_upload(b"\x7fELF\x02\x01\x01" + b"\x00" * 32, "binario.pdf")


# --- Storage -----------------------------------------------------------


def test_storage_key_ignores_user_file_name(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    key = storage.build_key(uuid4(), uuid4(), 1, ".pdf")

    assert "contrato" not in key
    assert key.endswith(".pdf")
    assert ".." not in key


@pytest.mark.asyncio
async def test_storage_rejects_path_traversal(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)

    with pytest.raises(StorageError):
        await storage.read("../../etc/passwd")


@pytest.mark.asyncio
async def test_storage_round_trip(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    key = storage.build_key(uuid4(), uuid4(), 1, ".pdf")
    stored = await storage.write(key, PDF_BYTES)

    assert await storage.read(key) == PDF_BYTES
    assert await storage.exists(key) is True
    assert stored.sha256 == sha256(PDF_BYTES).hexdigest()
    assert stored.size_bytes == len(PDF_BYTES)
    assert stored.tier is StorageTier.HOT


@pytest.mark.asyncio
async def test_storage_write_is_atomic(tmp_path: Path) -> None:
    """No partial file is left behind that could look like a valid document."""
    storage = LocalStorage(tmp_path)
    key = storage.build_key(uuid4(), uuid4(), 1, ".pdf")
    await storage.write(key, PDF_BYTES)

    partials = list(tmp_path.rglob("*.partial"))
    assert partials == []


@pytest.mark.asyncio
async def test_storage_delete_is_idempotent(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    key = storage.build_key(uuid4(), uuid4(), 1, ".pdf")
    await storage.write(key, PDF_BYTES)

    await storage.delete(key)
    await storage.delete(key)

    assert await storage.exists(key) is False


@pytest.mark.asyncio
async def test_local_storage_has_no_native_tiers(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    key = storage.build_key(uuid4(), uuid4(), 1, ".pdf")
    await storage.write(key, PDF_BYTES)

    assert storage.supports_native_tiers() is False
    applied = await storage.set_tier(
        key, StorageTier.ARCHIVE, expected_sha256=sha256(PDF_BYTES).hexdigest()
    )
    assert applied is False
    assert await storage.read(key) == PDF_BYTES


@pytest.mark.asyncio
async def test_local_tier_change_detects_corrupted_content(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    key = storage.build_key(uuid4(), uuid4(), 1, ".pdf")
    await storage.write(key, PDF_BYTES)

    with pytest.raises(StorageError):
        await storage.set_tier(key, StorageTier.ARCHIVE, expected_sha256="0" * 64)


@pytest.mark.asyncio
async def test_storage_rejects_sibling_directory_escape(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    root.mkdir()
    sibling = tmp_path / "storage-escape"
    sibling.mkdir()
    (sibling / "secreto.txt").write_text("no accesible")

    storage = LocalStorage(root)

    with pytest.raises(StorageError):
        await storage.read("../storage-escape/secreto.txt")


# --- API ---------------------------------------------------------------


@pytest.fixture(autouse=True)
def _temporary_document_storage(document_storage: LocalStorage) -> None:
    """Make every test in this module run against a temporary storage root.

    Endpoints build their own `DocumentService`, so the patch has to be active
    for the whole module rather than per test signature.
    """


async def test_create_document(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    response = await client.post(
        f"/api/v1/cases/{sample_case.id}/documents",
        json=_document(str(sample_case.id)),
        headers=_auth(admin_token),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "borrador"
    assert payload["version_count"] == 0
    assert payload["case_number"] == sample_case.case_number


async def test_create_document_requires_matching_case(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    response = await client.post(
        f"/api/v1/cases/{sample_case.id}/documents",
        json=_document(str(uuid4())),
        headers=_auth(admin_token),
    )

    assert response.status_code == 422


async def test_document_outside_scope_is_hidden(
    client: AsyncClient, other_case: Case, second_lawyer_token: tuple[object, str]
) -> None:
    _lawyer, token = second_lawyer_token
    response = await client.post(
        f"/api/v1/cases/{other_case.id}/documents",
        json=_document(str(other_case.id)),
        headers=_auth(token),
    )

    assert response.status_code == 404


async def test_upload_first_version_sets_current(
    client: AsyncClient, admin_token: str, sample_document: Document
) -> None:
    response = await client.post(
        f"{DOCUMENTS}/{sample_document.id}/versions",
        files={"file": ("contrato.pdf", PDF_BYTES, "application/pdf")},
        data={"notes": "Primera version firmada"},
        headers=_auth(admin_token),
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["version_number"] == 1
    assert payload["is_current"] is True
    assert payload["sha256"] == sha256(PDF_BYTES).hexdigest()
    assert payload["mime_type"] == "application/pdf"


async def test_new_version_never_replaces_the_previous(
    client: AsyncClient, admin_token: str, sample_document: Document
) -> None:
    first = await client.post(
        f"{DOCUMENTS}/{sample_document.id}/versions",
        files={"file": ("v1.pdf", PDF_BYTES, "application/pdf")},
        headers=_auth(admin_token),
    )
    second_bytes = PDF_BYTES + b"\n% segunda version"
    second = await client.post(
        f"{DOCUMENTS}/{sample_document.id}/versions",
        files={"file": ("v2.pdf", second_bytes, "application/pdf")},
        headers=_auth(admin_token),
    )
    detail = await client.get(f"{DOCUMENTS}/{sample_document.id}", headers=_auth(admin_token))

    assert second.json()["version_number"] == 2
    versions = detail.json()["versions"]
    assert [item["version_number"] for item in versions] == [1, 2]
    assert [item["is_current"] for item in versions] == [False, True]
    assert versions[0]["sha256"] == first.json()["sha256"]
    assert versions[0]["sha256"] != versions[1]["sha256"]
    assert detail.json()["current_version"] == 2


async def test_duplicate_content_is_rejected(
    client: AsyncClient, admin_token: str, sample_document: Document
) -> None:
    await client.post(
        f"{DOCUMENTS}/{sample_document.id}/versions",
        files={"file": ("v1.pdf", PDF_BYTES, "application/pdf")},
        headers=_auth(admin_token),
    )

    response = await client.post(
        f"{DOCUMENTS}/{sample_document.id}/versions",
        files={"file": ("copia.pdf", PDF_BYTES, "application/pdf")},
        headers=_auth(admin_token),
    )

    assert response.status_code == 409
    assert "ya existe" in response.json()["error"]["message"]


async def test_executable_upload_is_rejected(
    client: AsyncClient, admin_token: str, sample_document: Document
) -> None:
    response = await client.post(
        f"{DOCUMENTS}/{sample_document.id}/versions",
        files={"file": ("virus.pdf", EXE_BYTES, "application/pdf")},
        headers=_auth(admin_token),
    )

    assert response.status_code == 409
    assert "no permitido" in response.json()["error"]["message"]


async def test_anulled_document_rejects_new_versions(
    client: AsyncClient, admin_token: str, sample_document: Document
) -> None:
    await client.patch(
        f"{DOCUMENTS}/{sample_document.id}",
        json={"status": "anulado"},
        headers=_auth(admin_token),
    )

    response = await client.post(
        f"{DOCUMENTS}/{sample_document.id}/versions",
        files={"file": ("v1.pdf", PDF_BYTES, "application/pdf")},
        headers=_auth(admin_token),
    )

    assert response.status_code == 409


async def test_download_is_audited(
    client: AsyncClient,
    admin_user: User,
    admin_token: str,
    sample_document: Document,
    database_session: AsyncSession,
) -> None:
    version = await client.post(
        f"{DOCUMENTS}/{sample_document.id}/versions",
        files={"file": ("contrato.pdf", PDF_BYTES, "application/pdf")},
        headers=_auth(admin_token),
    )

    download = await client.get(
        f"{DOCUMENTS}/{sample_document.id}/versions/{version.json()['id']}/download",
        headers=_auth(admin_token),
    )

    assert download.status_code == 200
    assert download.content == PDF_BYTES
    assert download.headers["content-type"].startswith("application/pdf")
    assert download.headers["x-content-sha256"] == sha256(PDF_BYTES).hexdigest()
    assert download.headers["x-document-version"] == "1"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["cache-control"] == "no-store"
    assert "attachment" in download.headers["content-disposition"]
    assert "contrato.pdf" in download.headers["content-disposition"]

    records = list(
        (
            await database_session.execute(
                select(DocumentDownload).where(
                    DocumentDownload.document_id == sample_document.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(records) == 1
    assert records[0].user_id == admin_user.id
    assert records[0].ip_address == "127.0.0.1"
    assert records[0].version_id == UUID(version.json()["id"])


async def test_download_sanitises_the_untrusted_file_name(
    client: AsyncClient, admin_token: str, sample_document: Document
) -> None:
    version = await client.post(
        f"{DOCUMENTS}/{sample_document.id}/versions",
        files={"file": ("../../etc/pa\"sswd.txt", b"contenido", "text/plain")},
        headers=_auth(admin_token),
    )

    download = await client.get(
        f"{DOCUMENTS}/{sample_document.id}/versions/{version.json()['id']}/download",
        headers=_auth(admin_token),
    )

    disposition = download.headers["content-disposition"]
    assert download.status_code == 200
    assert "/" not in disposition.split(";")[1]
    assert "\r" not in disposition
    assert "\n" not in disposition


async def test_client_can_read_published_but_not_download(
    client: AsyncClient,
    admin_token: str,
    portal_user: tuple[User, Client],
    portal_token: str,
    database_session: AsyncSession,
) -> None:
    _user, portal_client = portal_user
    case = Case(
        case_number="WA-2026-000300",
        title="Expediente con documento",
        client_id=portal_client.id,
        process_type="civil",
        status="abierto",
        priority="normal",
        opened_at=date(2026, 5, 1),
        is_active=True,
    )
    database_session.add(case)
    await database_session.flush()

    document = await client.post(
        f"/api/v1/cases/{case.id}/documents",
        json=_document(str(case.id), visibility="publicada", title="Contrato publicado"),
        headers=_auth(admin_token),
    )
    version = await client.post(
        f"{DOCUMENTS}/{document.json()['id']}/versions",
        files={"file": ("contrato.pdf", PDF_BYTES, "application/pdf")},
        headers=_auth(admin_token),
    )

    listed = await client.get(
        f"/api/v1/cases/{case.id}/documents", headers=_auth(portal_token)
    )
    download = await client.get(
        f"{DOCUMENTS}/{document.json()['id']}/versions/{version.json()['id']}/download",
        headers=_auth(portal_token),
    )

    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert download.status_code == 403


async def test_client_does_not_see_internal_documents(
    client: AsyncClient,
    admin_token: str,
    portal_user: tuple[User, Client],
    portal_token: str,
    database_session: AsyncSession,
) -> None:
    _user, portal_client = portal_user
    case = Case(
        case_number="WA-2026-000301",
        title="Expediente con documento interno",
        client_id=portal_client.id,
        process_type="civil",
        status="abierto",
        priority="normal",
        opened_at=date(2026, 5, 2),
        is_active=True,
    )
    database_session.add(case)
    await database_session.flush()
    internal = await client.post(
        f"/api/v1/cases/{case.id}/documents",
        json=_document(str(case.id), visibility="interna", title="Documento interno"),
        headers=_auth(admin_token),
    )

    listed = await client.get(
        f"/api/v1/cases/{case.id}/documents", headers=_auth(portal_token)
    )
    detail = await client.get(
        f"{DOCUMENTS}/{internal.json()['id']}", headers=_auth(portal_token)
    )

    assert internal.status_code == 201
    assert listed.json() == []
    assert detail.status_code == 404


async def test_history_records_metadata_changes(
    client: AsyncClient, admin_token: str, sample_document: Document
) -> None:
    await client.patch(
        f"{DOCUMENTS}/{sample_document.id}",
        json={"title": "Contrato de servicios 2026", "confidentiality": "confidencial"},
        headers=_auth(admin_token),
    )

    history = await client.get(
        f"{DOCUMENTS}/{sample_document.id}/history", headers=_auth(admin_token)
    )

    assert history.status_code == 200
    fields = {entry["field_name"] for entry in history.json()}
    assert {"title", "confidentiality"} <= fields


async def test_list_documents_filters(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    await client.post(
        f"/api/v1/cases/{sample_case.id}/documents",
        json=_document(str(sample_case.id), document_type="demanda", title="Demanda"),
        headers=_auth(admin_token),
    )
    await client.post(
        f"/api/v1/cases/{sample_case.id}/documents",
        json=_document(str(sample_case.id), document_type="sentencia", title="Sentencia"),
        headers=_auth(admin_token),
    )

    by_type = await client.get(
        f"/api/v1/cases/{sample_case.id}/documents",
        params={"document_type": "demanda"},
        headers=_auth(admin_token),
    )
    all_documents = await client.get(
        f"/api/v1/cases/{sample_case.id}/documents", headers=_auth(admin_token)
    )

    assert by_type.json() != []
    assert len(by_type.json()) == 1
    assert len(all_documents.json()) == 2


async def test_case_360_includes_documents(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    await client.post(
        f"/api/v1/cases/{sample_case.id}/documents",
        json=_document(str(sample_case.id)),
        headers=_auth(admin_token),
    )

    response = await client.get(
        f"/api/v1/cases/{sample_case.id}/360", headers=_auth(admin_token)
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["documentos"]["available"] is True
    assert payload["documentos_total"] == 1
    assert payload["evidencias"]["available"] is True
    assert payload["evidencias_total"] == 0


async def test_anonymous_cannot_list_documents(client: AsyncClient) -> None:
    response = await client.get(f"{DOCUMENTS}/{uuid4()}")

    assert response.status_code == 401


async def test_download_unknown_version_returns_404(
    client: AsyncClient, admin_token: str, sample_document: Document
) -> None:
    response = await client.get(
        f"{DOCUMENTS}/{sample_document.id}/versions/{uuid4()}/download",
        headers=_auth(admin_token),
    )

    assert response.status_code == 404


async def test_service_rejects_document_on_unknown_case(
    database_session: AsyncSession, sample_document: Document
) -> None:
    service = DocumentService(database_session)

    with pytest.raises(DocumentError) as excinfo:
        await service.create_document(
            DocumentCreate(
                case_id=uuid4(),
                document_type="otro",
                title="Documento sin expediente",
            )
        )

    assert "expediente" in str(excinfo.value)


# --- Global browser ------------------------------------------------------


async def test_browse_documents_returns_a_paginated_page(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    await client.post(
        f"/api/v1/cases/{sample_case.id}/documents",
        json=_document(str(sample_case.id)),
        headers=_auth(admin_token),
    )

    response = await client.get(DOCUMENTS, headers=_auth(admin_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["skip"] == 0
    assert payload["limit"] == 50
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["title"] == "Contrato de servicios"
    assert payload["items"][0]["case_number"] == sample_case.case_number


async def test_browse_documents_pages_without_losing_the_total(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    for index in range(3):
        await client.post(
            f"/api/v1/cases/{sample_case.id}/documents",
            json=_document(str(sample_case.id), title=f"Documento {index}"),
            headers=_auth(admin_token),
        )

    response = await client.get(
        DOCUMENTS,
        params={"skip": 2, "limit": 2},
        headers=_auth(admin_token),
    )

    payload = response.json()
    assert payload["total"] == 3
    assert payload["skip"] == 2
    assert len(payload["items"]) == 1


async def test_browse_documents_filters_by_type_and_search(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    await client.post(
        f"/api/v1/cases/{sample_case.id}/documents",
        json=_document(str(sample_case.id), document_type="demanda", title="Demanda"),
        headers=_auth(admin_token),
    )
    await client.post(
        f"/api/v1/cases/{sample_case.id}/documents",
        json=_document(str(sample_case.id), document_type="sentencia", title="Sentencia"),
        headers=_auth(admin_token),
    )

    by_type = await client.get(
        DOCUMENTS,
        params={"document_type": "demanda"},
        headers=_auth(admin_token),
    )
    by_title = await client.get(
        DOCUMENTS, params={"search": "sentencia"}, headers=_auth(admin_token)
    )
    by_case_number = await client.get(
        DOCUMENTS,
        params={"search": sample_case.case_number},
        headers=_auth(admin_token),
    )

    assert [item["title"] for item in by_type.json()["items"]] == ["Demanda"]
    assert [item["title"] for item in by_title.json()["items"]] == ["Sentencia"]
    assert by_case_number.json()["total"] == 2


async def test_browse_documents_hides_cases_outside_the_scope(
    client: AsyncClient,
    admin_token: str,
    sample_case: Case,
    other_case: Case,
    second_lawyer_token: tuple[object, str],
) -> None:
    for case in (sample_case, other_case):
        await client.post(
            f"/api/v1/cases/{case.id}/documents",
            json=_document(str(case.id)),
            headers=_auth(admin_token),
        )

    _lawyer, token = second_lawyer_token
    response = await client.get(DOCUMENTS, headers=_auth(token))

    assert response.status_code == 200
    assert response.json()["total"] == 0


# --- The identifier path must obey the same scope as the listing ----------
#
# The listing filtered by case and the detail by identifier did not, so a lawyer
# with no assignments saw an empty list and could still read any document in the
# firm by guessing its UUID. `test_browse_documents_hides_cases_outside_the_scope`
# covers the list and proves nothing about this: an empty list and a reachable
# record are only distinguishable by asking for the record.


async def test_a_document_outside_the_scope_is_not_readable_by_identifier(
    client: AsyncClient,
    admin_token: str,
    other_case: Case,
    second_lawyer_token: tuple[object, str],
) -> None:
    created = await client.post(
        f"/api/v1/cases/{other_case.id}/documents",
        json=_document(str(other_case.id)),
        headers=_auth(admin_token),
    )
    document_id = created.json()["id"]

    _lawyer, token = second_lawyer_token
    response = await client.get(f"/api/v1/documents/{document_id}", headers=_auth(token))

    # 404 and not 403: a 403 confirms the record exists.
    assert response.status_code == 404


async def test_a_document_outside_the_scope_cannot_be_edited_by_identifier(
    client: AsyncClient,
    admin_token: str,
    other_case: Case,
    second_lawyer_token: tuple[object, str],
) -> None:
    created = await client.post(
        f"/api/v1/cases/{other_case.id}/documents",
        json=_document(str(other_case.id)),
        headers=_auth(admin_token),
    )
    document_id = created.json()["id"]

    _lawyer, token = second_lawyer_token
    response = await client.patch(
        f"/api/v1/documents/{document_id}",
        json={"title": "Titulo reescrito por alguien sin alcance"},
        headers=_auth(token),
    )

    assert response.status_code == 404


async def test_a_document_outside_the_scope_cannot_be_downloaded_by_identifier(
    client: AsyncClient,
    admin_token: str,
    other_case: Case,
    second_lawyer_token: tuple[object, str],
) -> None:
    """The worst case: reading the bytes of another case's file."""
    created = await client.post(
        f"/api/v1/cases/{other_case.id}/documents",
        json=_document(str(other_case.id)),
        headers=_auth(admin_token),
    )
    document_id = created.json()["id"]
    uploaded = await client.post(
        f"/api/v1/documents/{document_id}/versions",
        files={"file": ("contrato.pdf", b"%PDF-1.4 contenido", "application/pdf")},
        headers=_auth(admin_token),
    )
    version_id = uploaded.json()["id"]

    _lawyer, token = second_lawyer_token
    response = await client.get(
        f"/api/v1/documents/{document_id}/versions/{version_id}/download",
        headers=_auth(token),
    )

    assert response.status_code == 404


async def test_a_document_history_outside_the_scope_is_not_readable(
    client: AsyncClient,
    admin_token: str,
    other_case: Case,
    second_lawyer_token: tuple[object, str],
) -> None:
    created = await client.post(
        f"/api/v1/cases/{other_case.id}/documents",
        json=_document(str(other_case.id)),
        headers=_auth(admin_token),
    )
    document_id = created.json()["id"]

    _lawyer, token = second_lawyer_token
    response = await client.get(
        f"/api/v1/documents/{document_id}/history", headers=_auth(token)
    )

    assert response.status_code == 404


async def test_a_client_cannot_read_another_clients_published_document(
    client: AsyncClient,
    admin_token: str,
    other_case: Case,
    portal_token: str,
    portal_user: tuple[User, Client],
) -> None:
    """Visibility `publicada` is not a licence to read the whole firm's published set.

    The client may read published documents, but only inside its own case scope.
    Without the scope clause it could read any published document in the firm.
    """
    created = await client.post(
        f"/api/v1/cases/{other_case.id}/documents",
        json=_document(str(other_case.id), visibility="publicada"),
        headers=_auth(admin_token),
    )
    document_id = created.json()["id"]

    _portal_user, portal_client = portal_user
    assert portal_client.id != other_case.client_id

    response = await client.get(
        f"/api/v1/documents/{document_id}", headers=_auth(portal_token)
    )

    assert response.status_code == 404


async def test_a_document_inside_the_scope_is_still_readable(
    client: AsyncClient,
    admin_token: str,
    sample_case: Case,
) -> None:
    """The fix must not close the door on the legitimate caller."""
    created = await client.post(
        f"/api/v1/cases/{sample_case.id}/documents",
        json=_document(str(sample_case.id)),
        headers=_auth(admin_token),
    )
    document_id = created.json()["id"]

    response = await client.get(
        f"/api/v1/documents/{document_id}", headers=_auth(admin_token)
    )

    assert response.status_code == 200
    assert response.json()["id"] == document_id


async def test_browse_documents_only_shows_published_to_the_client(
    client: AsyncClient,
    admin_token: str,
    portal_token: str,
    portal_case: Case,
    sample_case: Case,
) -> None:
    await client.post(
        f"/api/v1/cases/{portal_case.id}/documents",
        json=_document(str(portal_case.id), title="Publicado", visibility="publicada"),
        headers=_auth(admin_token),
    )
    await client.post(
        f"/api/v1/cases/{portal_case.id}/documents",
        json=_document(str(portal_case.id), title="Interno"),
        headers=_auth(admin_token),
    )
    # Another client's case, also published: the scope must still exclude it.
    await client.post(
        f"/api/v1/cases/{sample_case.id}/documents",
        json=_document(str(sample_case.id), title="Ajeno", visibility="publicada"),
        headers=_auth(admin_token),
    )

    response = await client.get(DOCUMENTS, headers=_auth(portal_token))

    payload = response.json()
    assert payload["total"] == 1
    assert [item["title"] for item in payload["items"]] == ["Publicado"]


async def test_browse_documents_visibility_filter_cannot_widen_access(
    client: AsyncClient,
    admin_token: str,
    portal_token: str,
    portal_case: Case,
) -> None:
    await client.post(
        f"/api/v1/cases/{portal_case.id}/documents",
        json=_document(str(portal_case.id), title="Interno"),
        headers=_auth(admin_token),
    )

    response = await client.get(
        DOCUMENTS, params={"visibility": "interna"}, headers=_auth(portal_token)
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_browse_documents_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(DOCUMENTS)

    assert response.status_code == 401


async def test_browse_documents_rejects_an_out_of_range_page(
    client: AsyncClient, admin_token: str
) -> None:
    response = await client.get(
        DOCUMENTS, params={"limit": 500}, headers=_auth(admin_token)
    )

    assert response.status_code == 422
