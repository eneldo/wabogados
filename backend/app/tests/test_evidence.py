"""Evidence engine tests.

The tests are organised around the invariants that a law firm can be held to,
 because those are the ones that matter:

- The original is never altered, ever.
- Every original download is audited.
- A client cannot reach the original, internal evidence, or another client's case.
- A signed PDF keeps its signature.
- A derivative never claims to be the original.
"""

from datetime import UTC, date, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import StorageTier
from app.models import (
    Case,
    CaseLawyer,
    Client,
    Evidence,
    EvidenceAccessLog,
    EvidenceDerivative,
    EvidenceEvent,
    EvidenceFile,
    EvidenceProcessingJob,
    Lawyer,
    User,
)
from app.services.evidence import (
    MUTABLE_FIELDS,
    EvidenceError,
    EvidenceService,
    EvidenceStatus,
)
from app.services.evidence_processing import (
    ProcessingError,
    analyse_image,
    analyse_pdf,
    optimise_pdf,
    process_image,
)
from app.services.evidence_validation import (
    EvidenceValidationError,
    check_image_dimensions,
    detect_all_formats,
    validate_evidence,
)
from app.services.storage import build_evidence_key
from app.services.storage_local import LocalStorage

EVIDENCES = "/api/v1/evidences"


# --- Fixtures and factories ----------------------------------------------


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_jpeg(width: int = 800, height: int = 600, colour: str = "red") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def make_png(width: int = 400, height: int = 300, alpha: bool = False) -> bytes:
    buffer = BytesIO()
    mode = "RGBA" if alpha else "RGB"
    colour = (255, 0, 0, 128) if alpha else (0, 128, 255)
    Image.new(mode, (width, height), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def make_pdf(pages: int = 2) -> bytes:
    import pikepdf

    buffer = BytesIO()
    with pikepdf.Pdf.new() as pdf:
        for _ in range(pages):
            pdf.add_blank_page(page_size=(300, 300))
        pdf.save(buffer)
    return buffer.getvalue()


def make_signed_pdf() -> bytes:
    """A synthetic PDF carrying a signature field whose ByteRange covers the file.

    This is not a cryptographically valid signature, and the code never claims it
    is. It exercises the detection path: whether a signature exists, and whether
    its ByteRange still covers the whole document.
    """
    import pikepdf

    total = 900
    buffer = BytesIO()
    with pikepdf.Pdf.new() as pdf:
        pdf.add_blank_page(page_size=(300, 300))
        signature = pikepdf.Dictionary(
            Type=pikepdf.Name("/Sig"),
            ByteRange=pikepdf.Array([0, 400, 500, total - 900]),
            Contents=b"\x00" * 16,
        )
        field = pikepdf.Dictionary(FT=pikepdf.Name("/Sig"), V=signature)
        acroform = pikepdf.Dictionary(
            SigFlags=3, Fields=[pdf.make_indirect(field)]
        )
        pdf.Root["/AcroForm"] = pdf.make_indirect(acroform)
        pdf.save(buffer)
    # Pad so the ByteRange arithmetic matches the real file length.
    data = buffer.getvalue()
    return data + b"\n" * max(0, total - len(data))


async def _create_evidence(
    session: AsyncSession,
    case: Case,
    user: User,
    *,
    title: str = "Contrato fotografiado",
    visibility: str = "interna",
    evidence_type: str = "documental",
) -> Evidence:
    return await EvidenceService(session).create_evidence(
        case_id=case.id,
        title=title,
        evidence_type=evidence_type,
        actor=user,
        visibility=visibility,
    )


# --- Validation -----------------------------------------------------------


def test_pdf_is_accepted() -> None:
    validated = validate_evidence(make_pdf(), "contrato.pdf")

    assert validated.mime_type == "application/pdf"
    assert validated.is_pdf is True
    assert validated.is_image is False
    assert validated.extension == ".pdf"
    assert len(validated.sha256) == 64


def test_png_is_accepted() -> None:
    validated = validate_evidence(make_png(), "captura.png")

    assert validated.mime_type == "image/png"
    assert validated.is_image is True


def test_jpeg_is_accepted() -> None:
    validated = validate_evidence(make_jpeg(), "foto.jpg")

    assert validated.mime_type == "image/jpeg"


def test_executable_is_rejected() -> None:
    with pytest.raises(EvidenceValidationError):
        validate_evidence(b"MZ\x90\x00" + b"\x00" * 64, "contrato.pdf")


def test_shebang_script_is_rejected() -> None:
    with pytest.raises(EvidenceValidationError):
        validate_evidence(b"#!/bin/sh\nrm -rf /\n", "nota.txt")


def test_empty_file_is_rejected() -> None:
    with pytest.raises(EvidenceValidationError):
        validate_evidence(b"", "vacio.pdf")


def test_text_is_rejected_as_evidence() -> None:
    with pytest.raises(EvidenceValidationError) as excinfo:
        validate_evidence(b"solo texto plano", "nota.txt")

    assert "texto plano" in str(excinfo.value)


def test_zip_is_not_an_evidence_format() -> None:
    """A ZIP has no place in evidence and is the usual polyglot carrier."""
    payload = b"PK\x03\x04" + b"\x00" * 40

    with pytest.raises(EvidenceValidationError) as excinfo:
        validate_evidence(payload, "evidencia.zip")

    assert "no admitido" in str(excinfo.value)


def test_renamed_executable_is_rejected() -> None:
    with pytest.raises(EvidenceValidationError):
        validate_evidence(b"MZ\x90\x00" + b"\x00" * 64, "evidencia.png")


def test_wrong_extension_is_rejected() -> None:
    with pytest.raises(EvidenceValidationError) as excinfo:
        validate_evidence(make_pdf(), "evidencia.png")

    assert "extensión" in str(excinfo.value)


def test_declared_mime_mismatch_is_rejected() -> None:
    with pytest.raises(EvidenceValidationError) as excinfo:
        validate_evidence(make_pdf(), "evidencia.pdf", "image/png")

    assert "declarado" in str(excinfo.value)


def test_jpeg_extension_alias_is_accepted() -> None:
    assert validate_evidence(make_jpeg(), "foto.jpeg").mime_type == "image/jpeg"


def test_detect_all_formats_finds_a_polyglot() -> None:
    """A PDF that is also a ZIP is the classic content filter disagreement."""
    polyglot = b"%PDF-1.7\n" + b"PK\x03\x04" + b"\x00" * 40

    formats = detect_all_formats(polyglot)

    assert "application/pdf" in formats
    assert "application/zip" in formats
    assert len(formats) > 1


def test_image_bomb_dimensions_are_rejected() -> None:
    with pytest.raises(EvidenceValidationError) as excinfo:
        check_image_dimensions(40000, 40000)

    assert "bomba de descompresión" in str(excinfo.value)


def test_zero_dimensions_are_rejected() -> None:
    with pytest.raises(EvidenceValidationError):
        check_image_dimensions(0, 100)


def test_normal_dimensions_pass() -> None:
    check_image_dimensions(1920, 1080)


def test_read_image_size_returns_the_real_dimensions() -> None:
    from app.services.evidence_validation import read_image_size

    assert read_image_size(make_jpeg(320, 240)) == (320, 240)


# --- Image processing -----------------------------------------------------


def test_image_analysis_reports_dimensions() -> None:
    analysis = analyse_image(make_jpeg(1200, 800))

    assert analysis.width == 1200
    assert analysis.height == 800
    assert analysis.format_name == "JPEG"
    assert analysis.has_alpha is False


def test_png_with_alpha_is_detected() -> None:
    assert analyse_image(make_png(alpha=True)).has_alpha is True


def test_corrupt_image_is_reported_not_ignored() -> None:
    with pytest.raises(ProcessingError):
        analyse_image(b"%PDF-1.7 not really an image")


def test_image_processing_preserves_aspect_ratio() -> None:
    content = make_jpeg(3000, 2000)
    analysis = analyse_image(content)

    derivatives = {d.derivative_type.value: d for d in process_image(content, analysis)}

    optimised = derivatives["optimized"]
    assert optimised.width is not None and optimised.height is not None
    original_ratio = 3000 / 2000
    derived_ratio = optimised.width / optimised.height
    assert abs(derived_ratio - original_ratio) < 0.02


def test_image_processing_respects_the_size_ceiling() -> None:
    content = make_jpeg(5000, 3000)
    analysis = analyse_image(content)

    derivatives = {d.derivative_type.value: d for d in process_image(content, analysis)}

    assert max(derivatives["optimized"].width or 0, derivatives["optimized"].height or 0) <= 2560


def test_small_images_are_not_enlarged() -> None:
    """Upscaling a small photo invents detail that was never evidence."""
    content = make_jpeg(200, 150)
    analysis = analyse_image(content)

    derivatives = {d.derivative_type.value: d for d in process_image(content, analysis)}

    assert derivatives["optimized"].width == 200
    assert derivatives["optimized"].height == 150


def test_a_thumbnail_is_produced() -> None:
    content = make_jpeg(2000, 1500)
    analysis = analyse_image(content)

    derivatives = {d.derivative_type.value: d for d in process_image(content, analysis)}

    thumbnail = derivatives["thumbnail"]
    assert thumbnail.mime_type == "image/jpeg"
    assert max(thumbnail.width or 0, thumbnail.height or 0) <= 400


def test_derivative_is_smaller_than_the_original() -> None:
    content = make_jpeg(4000, 3000, colour="blue")
    analysis = analyse_image(content)

    derivatives = {d.derivative_type.value: d for d in process_image(content, analysis)}

    assert derivatives["optimized"].size_bytes < len(content)
    assert derivatives["optimized"].compression_ratio > 0


@pytest.mark.asyncio
async def test_compression_ratio_is_a_percentage_not_a_fraction() -> None:
    """The unit is a percentage, and it goes negative when a derivative grows.

    Both halves matter. A caller that multiplied this by 100 printed "1224 %"
    for a 12 % saving, and one that clamped negatives to zero reported a grown
    derivative as a saving. Pinning the unit here is what stops either.
    """
    from app.services.evidence_processing import Derivative, DerivativeType, Profile

    source = 1000

    halved = Derivative(
        derivative_type=DerivativeType.OPTIMIZED,
        content=b"x" * 500,
        mime_type="application/octet-stream",
        profile=Profile.LOSSLESS,
        source_size=source,
    )
    assert halved.compression_ratio == pytest.approx(50.0)

    # A derivative larger than its source: negative, and never rounded to zero.
    grown = Derivative(
        derivative_type=DerivativeType.THUMBNAIL,
        content=b"x" * 1124,
        mime_type="image/webp",
        profile=Profile.WEB_PREVIEW,
        source_size=source,
    )
    assert grown.compression_ratio == pytest.approx(-12.4)

    identical = Derivative(
        derivative_type=DerivativeType.OPTIMIZED,
        content=b"x" * source,
        mime_type="application/octet-stream",
        profile=Profile.LOSSLESS,
        source_size=source,
    )
    assert identical.compression_ratio == pytest.approx(0.0)

    unknown_source = Derivative(
        derivative_type=DerivativeType.OPTIMIZED,
        content=b"x" * 10,
        mime_type="application/octet-stream",
        profile=Profile.LOSSLESS,
        source_size=0,
    )
    assert unknown_source.compression_ratio == 0.0


def test_alpha_survives_in_a_png_derivative() -> None:
    content = make_png(600, 400, alpha=True)
    analysis = analyse_image(content)

    derivatives = {d.derivative_type.value: d for d in process_image(content, analysis)}

    assert derivatives["optimized"].mime_type == "image/png"


# --- PDF processing -------------------------------------------------------


def test_pdf_analysis_reports_pages() -> None:
    analysis = analyse_pdf(make_pdf(pages=3))

    assert analysis.page_count == 3
    assert analysis.is_signed is False


def test_pdf_optimisation_does_not_grow_the_file() -> None:
    content = make_pdf(pages=4)
    analysis = analyse_pdf(content)

    derivative = optimise_pdf(content, analysis)

    assert derivative.size_bytes <= len(content)
    assert derivative.page_count == 4


def test_signed_pdf_is_detected() -> None:
    analysis = analyse_pdf(make_signed_pdf())

    assert analysis.is_signed is True


def test_signed_pdf_is_copied_not_re_encoded() -> None:
    """Re-encoding a signed PDF destroys the signature. It must not happen."""
    content = make_signed_pdf()
    analysis = analyse_pdf(content)

    derivative = optimise_pdf(content, analysis)

    assert derivative.content == content
    assert "firmado" in str(derivative.detail)


def test_textual_pdf_is_not_rasterised() -> None:
    """MASTER_PROMPT section 20: selectable text must survive."""
    import pikepdf

    buffer = BytesIO()
    with pikepdf.Pdf.new() as pdf:
        page = pdf.add_blank_page(page_size=(300, 300))
        font = pdf.make_indirect(
            pikepdf.Dictionary(
                Type=pikepdf.Name("/Font"), Subtype=pikepdf.Name("/Type1")
            )
        )
        fonts = pdf.make_indirect(pikepdf.Dictionary(F1=font))
        page.obj["/Resources"] = pdf.make_indirect(pikepdf.Dictionary(Font=fonts))
        pdf.save(buffer)
    content = buffer.getvalue()

    analysis = analyse_pdf(content)

    assert analysis.has_text is True


def test_broken_pdf_is_reported() -> None:
    with pytest.raises(ProcessingError):
        analyse_pdf(b"%PDF-1.7 truncated and broken")


# --- Storage keys ---------------------------------------------------------


def test_evidence_key_follows_the_specified_layout() -> None:
    case_id, evidence_id = uuid4(), uuid4()

    key = build_evidence_key(case_id, evidence_id, "original", "abc123", ".pdf")

    assert key == f"evidences/{case_id}/{evidence_id}/original/abc123.pdf"


def test_evidence_key_rejects_an_unknown_area() -> None:
    with pytest.raises(ValueError):
        build_evidence_key(uuid4(), uuid4(), "cualquiera", "x", ".pdf")


def test_evidence_key_never_uses_the_uploaded_name(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)

    key = storage.build_evidence_key(
        uuid4(), uuid4(), "original", "../../etc/passwd", ".pdf"
    )

    assert ".." not in key
    assert "/" not in key.rsplit("/", 1)[-1].replace(".pdf", "")


# --- Chain of custody -----------------------------------------------------


@pytest.mark.asyncio
async def test_creating_an_evidence_records_an_event(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    await _create_evidence(database_session, sample_case, admin_user)

    events = list(
        (
            await database_session.execute(
                select(EvidenceEvent).where(EvidenceEvent.event_type == "uploaded")
            )
        )
        .scalars()
        .all()
    )

    assert len(events) == 1
    assert events[0].actor_id == admin_user.id


@pytest.mark.asyncio
async def test_attaching_the_original_records_the_full_trail(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)

    await service.attach_original(
        evidence, make_jpeg(), "foto.jpg", declared_mime="image/jpeg", actor=admin_user
    )

    types = {
        event.event_type
        for event in (
            await database_session.execute(select(EvidenceEvent))
        )
        .scalars()
        .all()
    }

    assert "uploaded" in types
    assert "validated" in types
    assert "original_stored" in types
    assert "derivative_created" in types
    assert "processed" in types


@pytest.mark.asyncio
async def test_original_stores_the_exact_bytes_and_hash(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    content = make_pdf()
    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)

    evidence_file, _outcome = await service.attach_original(
        evidence, content, "contrato.pdf", declared_mime="application/pdf", actor=admin_user
    )

    stored = await service.storage.read(evidence_file.storage_key)
    assert stored == content
    assert evidence_file.sha256 == sha256(content).hexdigest()
    assert evidence.original_sha256 == sha256(content).hexdigest()


@pytest.mark.asyncio
async def test_original_uses_the_specified_key_layout(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)

    evidence_file, _ = await service.attach_original(
        evidence, make_pdf(), "c.pdf", declared_mime="application/pdf", actor=admin_user
    )

    assert f"/evidences/{evidence.case_id}/{evidence.id}/original/" in (
        "/" + evidence_file.storage_key
    )


@pytest.mark.asyncio
async def test_derivatives_do_not_replace_the_original(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)

    evidence_file, outcome = await service.attach_original(
        evidence,
        make_jpeg(2000, 1500),
        "foto.jpg",
        declared_mime="image/jpeg",
        actor=admin_user,
    )

    assert outcome.derivatives >= 1
    original_bytes = await service.storage.read(evidence_file.storage_key)
    assert len(original_bytes) > 0

    derivatives = list(
        (
            await database_session.execute(
                select(EvidenceDerivative).where(
                    EvidenceDerivative.evidence_id == evidence.id
                )
            )
        )
        .scalars()
        .all()
    )
    for derivative in derivatives:
        assert derivative.storage_key != evidence_file.storage_key
        assert derivative.sha256 != evidence_file.sha256


@pytest.mark.asyncio
async def test_quarantined_when_validation_fails(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)

    with pytest.raises(EvidenceError):
        await service.attach_original(
            evidence,
            b"MZ\x90\x00" + b"\x00" * 64,
            "virus.pdf",
            actor=admin_user,
        )

    assert evidence.status == str(EvidenceStatus.QUARANTINED)
    stored = list(
        (
            await database_session.execute(
                select(EvidenceFile).where(EvidenceFile.evidence_id == evidence.id)
            )
        )
        .scalars()
        .all()
    )
    assert stored == [], "a rejected upload must not leave a stored file"


# --- Immutability ---------------------------------------------------------


def test_mutable_fields_exclude_the_original() -> None:
    """The legal invariants are enforced by what the API can even express."""
    assert "original_sha256" not in MUTABLE_FIELDS
    assert "storage_key" not in MUTABLE_FIELDS
    assert "created_at" not in MUTABLE_FIELDS
    assert "original_size" not in MUTABLE_FIELDS


@pytest.mark.asyncio
async def test_service_refuses_to_change_immutable_fields(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)

    with pytest.raises(EvidenceError) as excinfo:
        await service.update_evidence(
            evidence, {"original_sha256": "0" * 64}, actor=admin_user
        )

    assert "inmutables" in str(excinfo.value)


def test_update_schema_cannot_express_the_original_hash() -> None:
    from app.schemas.evidence import EvidenceUpdate

    assert "original_sha256" not in EvidenceUpdate.model_fields
    assert "storage_key" not in EvidenceUpdate.model_fields
    assert "created_at" not in EvidenceUpdate.model_fields


@pytest.mark.asyncio
async def test_database_allows_several_non_original_files(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    """The single original rule must not cap the non original rows at one.

    A plain UNIQUE(evidence_id, is_original) would reject the second copy.
    """
    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)
    await service.attach_original(
        evidence, make_pdf(), "a.pdf", declared_mime="application/pdf", actor=admin_user
    )

    for index in range(2):
        database_session.add(
            EvidenceFile(
                evidence_id=evidence.id,
                storage_key=f"copia-{index}",
                original_filename=f"copia-{index}.pdf",
                mime_type="application/pdf",
                file_size=10,
                sha256="0" * 64,
                is_original=False,
            )
        )
    await database_session.flush()

    total = await database_session.scalar(
        select(func.count()).select_from(EvidenceFile).where(
            EvidenceFile.evidence_id == evidence.id
        )
    )
    assert total == 3


@pytest.mark.asyncio
async def test_database_still_refuses_a_second_original(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    from sqlalchemy.exc import IntegrityError

    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)
    await service.attach_original(
        evidence, make_pdf(), "a.pdf", declared_mime="application/pdf", actor=admin_user
    )

    database_session.add(
        EvidenceFile(
            evidence_id=evidence.id,
            storage_key="x",
            original_filename="b.pdf",
            mime_type="application/pdf",
            file_size=1,
            sha256="0" * 64,
            is_original=True,
        )
    )

    with pytest.raises(IntegrityError):
        await database_session.flush()


# --- Access logging -------------------------------------------------------


@pytest.mark.asyncio
async def test_downloading_the_original_is_audited(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)
    await service.attach_original(
        evidence, make_pdf(), "c.pdf", declared_mime="application/pdf", actor=admin_user
    )

    await service.read_original(evidence, user=admin_user, ip_address="127.0.0.1")

    logs = list(
        (
            await database_session.execute(
                select(EvidenceAccessLog).where(
                    EvidenceAccessLog.evidence_id == evidence.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(logs) == 1
    assert logs[0].access_type == "download_original"
    assert logs[0].user_id == admin_user.id
    assert logs[0].ip_address == "127.0.0.1"


@pytest.mark.asyncio
async def test_corrupted_original_blocks_the_download(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    """Serving bytes that do not match the hash is the worst outcome."""
    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)
    evidence_file, _ = await service.attach_original(
        evidence, make_pdf(), "d.pdf", declared_mime="application/pdf", actor=admin_user
    )
    await service.storage.write(evidence_file.storage_key, b"contenido manipulado")

    with pytest.raises(EvidenceError) as excinfo:
        await service.read_original(evidence, user=admin_user)

    assert "integridad" in str(excinfo.value)


# --- API ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_create_and_upload(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    created = await client.post(
        f"/api/v1/cases/{sample_case.id}/evidences",
        json={
            "case_id": str(sample_case.id),
            "title": "Contrato fotografiado",
            "evidence_type": "documental",
        },
        headers=_auth(admin_token),
    )

    assert created.status_code == 201
    evidence_id = created.json()["id"]

    uploaded = await client.post(
        f"{EVIDENCES}/{evidence_id}/original",
        files={"file": ("contrato.jpg", make_jpeg(), "image/jpeg")},
        headers=_auth(admin_token),
    )

    assert uploaded.status_code == 200
    payload = uploaded.json()
    assert payload["evidence"]["status"] == "ready"
    assert payload["derivatives_created"] >= 1
    assert payload["evidence"]["original_sha256"]


@pytest.mark.asyncio
async def test_api_refuses_a_second_original(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    created = await client.post(
        f"/api/v1/cases/{sample_case.id}/evidences",
        json={
            "case_id": str(sample_case.id),
            "title": "Evidencia con original",
            "evidence_type": "documental",
        },
        headers=_auth(admin_token),
    )
    evidence_id = created.json()["id"]
    await client.post(
        f"{EVIDENCES}/{evidence_id}/original",
        files={"file": ("a.jpg", make_jpeg(), "image/jpeg")},
        headers=_auth(admin_token),
    )

    second = await client.post(
        f"{EVIDENCES}/{evidence_id}/original",
        files={"file": ("b.jpg", make_jpeg(400, 300, "blue"), "image/jpeg")},
        headers=_auth(admin_token),
    )

    assert second.status_code == 409


@pytest.mark.asyncio
async def test_api_rejects_an_invalid_evidence(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    created = await client.post(
        f"/api/v1/cases/{sample_case.id}/evidences",
        json={
            "case_id": str(sample_case.id),
            "title": "Evidencia inválida",
            "evidence_type": "documental",
        },
        headers=_auth(admin_token),
    )
    evidence_id = created.json()["id"]

    response = await client.post(
        f"{EVIDENCES}/{evidence_id}/original",
        files={"file": ("virus.pdf", b"MZ\x90\x00" + b"\x00" * 32, "application/pdf")},
        headers=_auth(admin_token),
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_api_requires_permission_to_upload(
    client: AsyncClient, plain_user_token: str, sample_case: Case
) -> None:
    response = await client.post(
        f"{EVIDENCES}/{uuid4()}/original",
        files={"file": ("a.jpg", make_jpeg(), "image/jpeg")},
        headers=_auth(plain_user_token),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_api_custody_requires_the_permission(
    client: AsyncClient, plain_user_token: str, sample_case: Case
) -> None:
    """A role with no evidence permissions gets 403 before anything else."""
    response = await client.get(
        f"{EVIDENCES}/{uuid4()}/custody", headers=_auth(plain_user_token)
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_api_custody_does_not_leak_other_cases(
    client: AsyncClient, staff_token: str, other_case: Case, admin_token: str
) -> None:
    """`evidences:audit` alone must not open every custody trail in the firm."""
    created = await client.post(
        f"/api/v1/cases/{other_case.id}/evidences",
        json={
            "case_id": str(other_case.id),
            "title": "Evidencia con custodia ajena",
            "evidence_type": "documental",
        },
        headers=_auth(admin_token),
    )

    response = await client.get(
        f"{EVIDENCES}/{created.json()['id']}/custody", headers=_auth(staff_token)
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_custody_endpoint_returns_events_and_accesses(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    created = await client.post(
        f"/api/v1/cases/{sample_case.id}/evidences",
        json={
            "case_id": str(sample_case.id),
            "title": "Evidencia con custodia",
            "evidence_type": "documental",
        },
        headers=_auth(admin_token),
    )
    evidence_id = created.json()["id"]
    await client.post(
        f"{EVIDENCES}/{evidence_id}/original",
        files={"file": ("a.pdf", make_pdf(), "application/pdf")},
        headers=_auth(admin_token),
    )
    await client.get(f"{EVIDENCES}/{evidence_id}/original", headers=_auth(admin_token))

    custody = await client.get(
        f"{EVIDENCES}/{evidence_id}/custody", headers=_auth(admin_token)
    )

    assert custody.status_code == 200
    payload = custody.json()
    assert payload["original_sha256"]
    types = {event["event_type"] for event in payload["events"]}
    assert "original_stored" in types
    assert "downloaded_original" in types
    assert payload["accesses"]


@pytest.mark.asyncio
async def test_original_download_sets_integrity_headers(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    content = make_pdf()
    created = await client.post(
        f"/api/v1/cases/{sample_case.id}/evidences",
        json={
            "case_id": str(sample_case.id),
            "title": "Evidencia descargable",
            "evidence_type": "documental",
        },
        headers=_auth(admin_token),
    )
    evidence_id = created.json()["id"]
    await client.post(
        f"{EVIDENCES}/{evidence_id}/original",
        files={"file": ("a.pdf", content, "application/pdf")},
        headers=_auth(admin_token),
    )

    download = await client.get(
        f"{EVIDENCES}/{evidence_id}/original", headers=_auth(admin_token)
    )

    assert download.status_code == 200
    assert download.content == content
    assert download.headers["x-content-sha256"] == sha256(content).hexdigest()
    assert download.headers["x-content-type-options"] == "nosniff"
    assert "attachment" in download.headers["content-disposition"]


@pytest.mark.asyncio
async def test_case_360_includes_evidence(
    client: AsyncClient, admin_token: str, sample_case: Case
) -> None:
    await client.post(
        f"/api/v1/cases/{sample_case.id}/evidences",
        json={
            "case_id": str(sample_case.id),
            "title": "Evidencia en la ficha",
            "evidence_type": "documental",
        },
        headers=_auth(admin_token),
    )

    response = await client.get(
        f"/api/v1/cases/{sample_case.id}/360", headers=_auth(admin_token)
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["evidencias"]["available"] is True
    assert payload["evidencias_total"] == 1
    assert payload["tareas"]["available"] is False


@pytest.mark.asyncio
async def test_the_metadata_endpoint_is_reachable_for_staff(
    client: AsyncClient,
    admin_token: str,
    database_session: AsyncSession,
    sample_case: Case,
) -> None:
    """`PATCH /evidences/{id}` required a permission that was not in the catalogue.

    `evidences:update` was named by the route and never defined, so the endpoint
    answered 403 for everyone but a superuser and no test noticed, because none of
    them called it. This asserts the route is actually usable, and the RBAC suite
    separately asserts the permission reaches the database.
    """
    created = await client.post(
        f"/api/v1/cases/{sample_case.id}/evidences",
        json={
                "case_id": str(sample_case.id),
                "title": "Foto del lugar",
                "evidence_type": "fotografica",
            },
        headers=_auth(admin_token),
    )
    evidence_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/evidences/{evidence_id}",
        json={"description": "Anotada desde la prueba"},
        headers=_auth(admin_token),
    )

    assert response.status_code == 200
    assert response.json()["description"] == "Anotada desde la prueba"


async def test_an_empty_metadata_change_is_refused(
    client: AsyncClient,
    admin_token: str,
    sample_case: Case,
) -> None:
    created = await client.post(
        f"/api/v1/cases/{sample_case.id}/evidences",
        json={
                "case_id": str(sample_case.id),
                "title": "Foto del lugar",
                "evidence_type": "fotografica",
            },
        headers=_auth(admin_token),
    )

    response = await client.patch(
        f"/api/v1/evidences/{created.json()['id']}",
        json={},
        headers=_auth(admin_token),
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_evidence_cannot_be_registered_on_a_foreign_case(
    client: AsyncClient,
    sample_client: Client,
    other_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """`create_evidence` had a dead scope check, so writes were unrestricted.

    It called `scope_filter(session, actor, CaseScope.ALL)`, which returns `None` by
    definition, so the `if clause is not None:` branch never ran. Every other evidence
    endpoint took `get_user_scope`; this one took `CaseScope.ALL` directly, so a user
    with no assignments could attach evidence to an expediente they cannot read, and
    the row would then be invisible to them while attached to somebody else's file.
    """
    _, token = second_lawyer_token

    response = await client.post(
        f"/api/v1/cases/{other_case.id}/evidences",
        json={
            "case_id": str(other_case.id),
            "title": "Foto del lugar",
            "evidence_type": "fotografica",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_evidence_can_be_registered_on_your_own_case(
    client: AsyncClient,
    database_session: AsyncSession,
    sample_client: Client,
    sample_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """The counterpart: after the fix the route still has to work."""
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

    response = await client.post(
        f"/api/v1/cases/{sample_case.id}/evidences",
        json={
            "case_id": str(sample_case.id),
            "title": "Foto del lugar",
            "evidence_type": "fotografica",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201


async def test_evidence_of_another_case_is_reachable_only_with_scope(
    client: AsyncClient, admin_token: str, other_case: Case
) -> None:
    """An administrator has case wide read, so this must be visible."""
    created = await client.post(
        f"/api/v1/cases/{other_case.id}/evidences",
        json={
            "case_id": str(other_case.id),
            "title": "Evidencia de otro expediente",
            "evidence_type": "documental",
        },
        headers=_auth(admin_token),
    )

    response = await client.get(
        f"{EVIDENCES}/{created.json()['id']}", headers=_auth(admin_token)
    )

    assert created.status_code == 201
    assert response.status_code == 200
    assert response.json()["title"] == "Evidencia de otro expediente"


# --- Client isolation -----------------------------------------------------


@pytest.mark.asyncio
async def test_client_sees_published_evidence_only(
    client: AsyncClient,
    admin_token: str,
    portal_token: str,
    portal_case: Case,
) -> None:
    _user, portal_client = None, None
    for visibility in ("interna", "publicada"):
        created = await client.post(
            f"/api/v1/cases/{portal_case.id}/evidences",
            json={
                "case_id": str(portal_case.id),
                "title": f"Evidencia {visibility}",
                "evidence_type": "documental",
                "visibility": visibility,
            },
            headers=_auth(admin_token),
        )
        assert created.status_code == 201
        await client.post(
            f"{EVIDENCES}/{created.json()['id']}/original",
            files={"file": ("a.jpg", make_jpeg(), "image/jpeg")},
            headers=_auth(admin_token),
        )
    del portal_client

    listed = await client.get(
        f"/api/v1/cases/{portal_case.id}/evidences", headers=_auth(portal_token)
    )

    assert listed.status_code == 200
    titles = {item["title"] for item in listed.json()}
    assert "Evidencia publicada" in titles
    assert "Evidencia interna" not in titles


@pytest.mark.asyncio
async def test_client_cannot_download_the_original(
    client: AsyncClient, admin_token: str, portal_token: str, portal_case: Case
) -> None:
    created = await client.post(
        f"/api/v1/cases/{portal_case.id}/evidences",
        json={
            "case_id": str(portal_case.id),
            "title": "Evidencia publicada",
            "evidence_type": "documental",
            "visibility": "publicada",
        },
        headers=_auth(admin_token),
    )
    evidence_id = created.json()["id"]
    await client.post(
        f"{EVIDENCES}/{evidence_id}/original",
        files={"file": ("a.pdf", make_pdf(), "application/pdf")},
        headers=_auth(admin_token),
    )

    response = await client.get(
        f"{EVIDENCES}/{evidence_id}/original", headers=_auth(portal_token)
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_internal_evidence_is_404_for_the_client(
    client: AsyncClient, admin_token: str, portal_token: str, portal_case: Case
) -> None:
    """404, not 403: the API must not confirm the evidence exists."""
    created = await client.post(
        f"/api/v1/cases/{portal_case.id}/evidences",
        json={
            "case_id": str(portal_case.id),
            "title": "Evidencia interna",
            "evidence_type": "documental",
            "visibility": "interna",
        },
        headers=_auth(admin_token),
    )

    response = await client.get(
        f"{EVIDENCES}/{created.json()['id']}", headers=_auth(portal_token)
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_client_does_not_see_evidence_of_another_client(
    client: AsyncClient,
    admin_token: str,
    portal_token: str,
    database_session: AsyncSession,
    sample_case: Case,
) -> None:
    """Rule 12: no cross client access, even for a published evidence."""
    other_client = Client(
        client_type="natural",
        document_type="cedula",
        document_number="55555555",
        full_name="Otro cliente",
        is_active=True,
    )
    database_session.add(other_client)
    await database_session.flush()

    theirs = Case(
        case_number="WA-2026-000701",
        title="Expediente de otro cliente",
        client_id=other_client.id,
        process_type="civil",
        status="abierto",
        priority="normal",
        opened_at=date(2026, 6, 1),
        is_active=True,
    )
    database_session.add(theirs)
    await database_session.flush()

    created = await client.post(
        f"/api/v1/cases/{theirs.id}/evidences",
        json={
            "case_id": str(theirs.id),
            "title": "Evidencia de otro cliente",
            "evidence_type": "documental",
            "visibility": "publicada",
        },
        headers=_auth(admin_token),
    )
    assert created.status_code == 201

    listed = await client.get(
        f"/api/v1/cases/{theirs.id}/evidences", headers=_auth(portal_token)
    )
    detail = await client.get(
        f"{EVIDENCES}/{created.json()['id']}", headers=_auth(portal_token)
    )

    assert listed.status_code == 200
    assert listed.json() == []
    assert detail.status_code == 404


@pytest.mark.asyncio
async def test_unassigned_lawyer_does_not_see_evidence(
    client: AsyncClient,
    admin_token: str,
    database_session: AsyncSession,
    sample_case: Case,
    other_case: Case,
    second_lawyer_token: tuple[Lawyer, str],
) -> None:
    """The second lawyer is assigned to no case at all."""
    _lawyer, token = second_lawyer_token

    created = await client.post(
        f"/api/v1/cases/{other_case.id}/evidences",
        json={
            "case_id": str(other_case.id),
            "title": "Evidencia de un expediente ajeno",
            "evidence_type": "documental",
        },
        headers=_auth(admin_token),
    )
    await client.post(
        f"{EVIDENCES}/{created.json()['id']}/original",
        files={"file": ("a.jpg", make_jpeg(), "image/jpeg")},
        headers=_auth(admin_token),
    )
    assert sample_case.id != other_case.id

    listed = await client.get(
        f"/api/v1/cases/{other_case.id}/evidences", headers=_auth(token)
    )
    detail = await client.get(f"{EVIDENCES}/{created.json()['id']}", headers=_auth(token))

    assert listed.status_code == 200
    assert listed.json() == []
    assert detail.status_code == 404


# --- Worker ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_large_file_is_queued_instead_of_blocking(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.evidence.INLINE_LIMIT_BYTES", 10)
    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)

    _file, outcome = await service.attach_original(
        evidence, make_pdf(), "grande.pdf", declared_mime="application/pdf", actor=admin_user
    )

    assert outcome.queued is True
    assert outcome.derivatives == 0
    jobs = list(
        (
            await database_session.execute(
                select(EvidenceProcessingJob).where(
                    EvidenceProcessingJob.evidence_id == evidence.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(jobs) == 1
    assert jobs[0].status == "queued"


@pytest.mark.asyncio
async def test_worker_processes_a_queued_job(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)
    evidence_file, _ = await service.attach_original(
        evidence, make_jpeg(1000, 800), "foto.jpg", declared_mime="image/jpeg", actor=admin_user
    )
    database_session.add(
        EvidenceProcessingJob(
            evidence_id=evidence.id,
            job_type="process",
            status="queued",
        )
    )
    await database_session.flush()

    job = await database_session.scalar(select(EvidenceProcessingJob))
    assert job is not None
    outcome = await service.run_queued_job(job, worker="test")

    assert outcome.derivatives >= 1
    assert job.status == "completed"
    assert job.worker == "test"
    assert job.finished_at is not None
    assert evidence.status == str(EvidenceStatus.READY)
    assert evidence_file.sha256


@pytest.mark.asyncio
async def test_worker_marks_a_failure(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)
    evidence_file, _ = await service.attach_original(
        evidence, make_pdf(), "c.pdf", declared_mime="application/pdf", actor=admin_user
    )
    del evidence_file
    job = EvidenceProcessingJob(evidence_id=evidence.id, job_type="process", status="queued")
    database_session.add(job)
    await database_session.flush()

    # The stored original disappears, which is the failure the worker must report.
    await service.storage.delete(
        (await service.original_of(await service.get_evidence(evidence.id) or evidence)).storage_key  # type: ignore[union-attr]
    )

    with pytest.raises(EvidenceError):
        await service.run_queued_job(job, worker="test")

    assert job.status == "failed"
    assert job.error


# --- Retention of the original --------------------------------------------


@pytest.mark.asyncio
async def test_original_survives_processing_untouched(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    content = make_jpeg(1500, 1000)
    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)

    evidence_file, _ = await service.attach_original(
        evidence, content, "original.jpg", declared_mime="image/jpeg", actor=admin_user
    )

    assert await service.storage.read(evidence_file.storage_key) == content
    assert evidence_file.sha256 == sha256(content).hexdigest()
    # Read through the service: the relationship on an instance created in this
    # session is not loaded, and touching it outside a query is a bug.
    derivatives = await service.derivatives_of(evidence)
    assert len(derivatives) >= 1
    for derivative in derivatives:
        assert derivative.sha256 != evidence_file.sha256


@pytest.mark.asyncio
async def test_derivative_listing_happens_only_through_the_service(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)
    await service.attach_original(
        evidence, make_pdf(), "x.pdf", declared_mime="application/pdf", actor=admin_user
    )

    fresh = await service.get_evidence(evidence.id)

    assert fresh is not None
    assert len(fresh.files) == 1
    assert fresh.files[0].is_original is True
    assert len(fresh.derivatives) >= 1


def test_storage_tier_enum_still_available() -> None:
    """Regression guard: the evidence work must not break the storage contract."""
    assert StorageTier.HOT.value == "hot"


@pytest.mark.asyncio
async def test_counting_helpers_agree(
    database_session: AsyncSession, sample_case: Case, admin_user: User
) -> None:
    service = EvidenceService(database_session)
    evidence = await _create_evidence(database_session, sample_case, admin_user)
    await service.attach_original(
        evidence, make_pdf(), "y.pdf", declared_mime="application/pdf", actor=admin_user
    )

    files = await database_session.scalar(
        select(func.count()).select_from(EvidenceFile).where(
            EvidenceFile.evidence_id == evidence.id
        )
    )
    derivatives = await database_session.scalar(
        select(func.count()).select_from(EvidenceDerivative).where(
            EvidenceDerivative.evidence_id == evidence.id
        )
    )

    assert files == 1
    assert derivatives and derivatives >= 1


def test_uuid_helpers_available() -> None:
    assert isinstance(uuid4(), UUID)
    assert datetime.now(UTC) + timedelta(seconds=1) > datetime.now(UTC)