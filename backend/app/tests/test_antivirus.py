"""Antivirus engine tests.

The three verdicts — clean, infected, engine down — are pinned at every place
the pipeline applies them: the inline evidence path, the queued evidence path
and the document version path. They also pin the policy decision of
2026-10-21: an infected copy is discarded, an infected evidence is marked
`quarantined` and keeps its custody trail, and an unavailable engine closes
the door instead of letting bytes through.
"""

import asyncio
import socket
import struct
from collections.abc import AsyncIterator
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    Case,
    Document,
    DocumentVersion,
    Evidence,
    EvidenceEvent,
    EvidenceFile,
    EvidenceProcessingJob,
    User,
)
from app.services.antivirus import (
    AntivirusUnavailable,
    ClamavScanner,
    Scanner,
    ScanResult,
    build_scanner,
)
from app.services.documents import DocumentError, DocumentService
from app.services.evidence import (
    EvidenceError,
    EvidenceService,
    EvidenceStatus,
    JobStatus,
)
from app.services.storage_local import LocalStorage

CLEAN = ScanResult(clean=True, signature=None, detail="stream: OK")
INFECTED = ScanResult(
    clean=False,
    signature="EICAR.Test.File-Test",
    detail="stream: EICAR.Test.File-Test FOUND",
)

#: The canonical ClamAV test signal, used by every fake engine below.
EICAR = b"EICAR-test-payload-decision-2026-10-21"


class FakeScanner(Scanner):
    """One preset verdict, recorded payloads, no network."""

    def __init__(self, result: ScanResult | AntivirusUnavailable) -> None:
        self.result = result
        self.payloads: list[bytes] = []

    async def scan(self, content: bytes) -> ScanResult:
        self.payloads.append(content)
        if isinstance(self.result, AntivirusUnavailable):
            raise self.result
        return self.result


# --- Fixtures -------------------------------------------------------------


def make_jpeg(width: int = 400, height: int = 300) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), "red").save(buffer, format="JPEG", quality=91)
    return buffer.getvalue()


async def _evidence_upload(
    database_session: AsyncSession,
    case: Case,
    actor: User,
    scanner: Scanner,
    tmp_path: Path,
) -> tuple[EvidenceService, Evidence, EvidenceFile]:
    """One evidence with its original attached, through the real pipeline."""
    service = EvidenceService(database_session, storage=LocalStorage(tmp_path), scanner=scanner)
    evidence = Evidence(
        case_id=case.id,
        title="Evidencia antivirus",
        evidence_type="documento",
        status=str(EvidenceStatus.UPLOADED),
        visibility="interna",
        confidentiality="interno",
        created_by=actor.id,
        is_active=True,
    )
    database_session.add(evidence)
    await database_session.flush()

    file, _ = await service.attach_original(
        evidence, make_jpeg(), "foto.jpg", declared_mime="image/jpeg", actor=actor
    )
    return service, evidence, file


# --- The INSTREAM client against fake clamd servers -----------------------


async def _clamd_handler(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    command = await reader.readexactly(len(b"zINSTREAM\x00"))
    assert command == b"zINSTREAM\x00"
    payload = bytearray()
    while True:
        (size,) = struct.unpack(">I", await reader.readexactly(4))
        if size == 0:
            break
        payload += await reader.readexactly(size)
    if b"EICAR" in payload:
        writer.write(b"stream: EICAR.Test.File-Test FOUND\n")
    else:
        writer.write(b"stream: OK\n")
    await writer.drain()
    writer.close()
    await writer.wait_closed()


async def _garbage_handler(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> None:
    command = await reader.readexactly(len(b"zINSTREAM\x00"))
    assert command == b"zINSTREAM\x00"
    while True:
        (size,) = struct.unpack(">I", await reader.readexactly(4))
        if size == 0:
            break
        await reader.readexactly(size)
    writer.write(b"PROXYERROR something the client cannot interpret\n")
    await writer.drain()
    writer.close()
    await writer.wait_closed()


@pytest.fixture
async def clamd_port() -> AsyncIterator[int]:
    """A fake clamd speaking the real responses for the test payloads."""
    server = await asyncio.start_server(_clamd_handler, "127.0.0.1", 0)
    yield int(server.sockets[0].getsockname()[1])
    server.close()
    await server.wait_closed()


@pytest.fixture
async def garbage_port() -> AsyncIterator[int]:
    """A listener that answers a line no verdict parser can interpret."""
    server = await asyncio.start_server(_garbage_handler, "127.0.0.1", 0)
    yield int(server.sockets[0].getsockname()[1])
    server.close()
    await server.wait_closed()


def _closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
        return port


async def test_clamd_clean_answer_is_a_clean_verdict(clamd_port: int) -> None:
    scanner = ClamavScanner("127.0.0.1", clamd_port, timeout=5.0)

    verdict = await scanner.scan(make_jpeg())

    assert verdict.clean is True
    assert verdict.signature is None
    assert verdict.detail.endswith("OK")


async def test_clamd_found_answer_names_the_signature(clamd_port: int) -> None:
    scanner = ClamavScanner("127.0.0.1", clamd_port, timeout=5.0)

    verdict = await scanner.scan(EICAR)

    assert verdict.clean is False
    assert verdict.signature == "EICAR.Test.File-Test"


async def test_an_uninterpretable_answer_is_not_an_implicit_clean(
    garbage_port: int,
) -> None:
    scanner = ClamavScanner("127.0.0.1", garbage_port, timeout=5.0)

    with pytest.raises(AntivirusUnavailable):
        await scanner.scan(make_jpeg())


async def test_a_refused_connection_is_the_engine_being_down() -> None:
    scanner = ClamavScanner("127.0.0.1", _closed_port(), timeout=2.0)

    with pytest.raises(AntivirusUnavailable):
        await scanner.scan(make_jpeg())


def test_no_host_means_no_engine() -> None:
    get_settings.cache_clear()
    try:
        assert build_scanner(get_settings()) is None
    finally:
        get_settings.cache_clear()


def test_a_host_builds_a_clamd_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTIVIRUS_HOST", "clamav.local")
    get_settings.cache_clear()
    try:
        scanner = build_scanner(get_settings())
    finally:
        get_settings.cache_clear()

    assert isinstance(scanner, ClamavScanner)
    assert scanner.host == "clamav.local"


# --- Evidence: inline path ------------------------------------------------


async def test_a_clean_inline_upload_is_ready_and_keeps_the_bytes(
    database_session: AsyncSession, sample_case: Case, admin_user: User, tmp_path: Path
) -> None:
    service, evidence, file = await _evidence_upload(
        database_session, sample_case, admin_user, FakeScanner(CLEAN), tmp_path
    )

    assert evidence.status == str(EvidenceStatus.READY)
    assert (await service.storage.stat(file.storage_key)) is not None


async def test_an_infected_inline_upload_is_quarantined_and_the_copy_is_gone(
    database_session: AsyncSession, sample_case: Case, admin_user: User, tmp_path: Path
) -> None:
    service, evidence, file = await _evidence_upload(
        database_session, sample_case, admin_user, FakeScanner(INFECTED), tmp_path
    )

    assert evidence.status == str(EvidenceStatus.QUARANTINED)
    assert (await service.storage.stat(file.storage_key)) is None

    events = (await database_session.execute(select(EvidenceEvent))).scalars().all()
    verdict_events = [e for e in events if e.event_type == "antivirus_infected"]
    assert len(verdict_events) == 1
    assert verdict_events[0].detail is not None
    assert verdict_events[0].detail.startswith("Positivo (EICAR.Test.File-Test)")
    assert "copia local descartada" in verdict_events[0].detail


async def test_an_infected_inline_upload_receives_the_verdict_in_the_outcome(
    database_session: AsyncSession, sample_case: Case, admin_user: User, tmp_path: Path
) -> None:
    service = EvidenceService(
        database_session, storage=LocalStorage(tmp_path), scanner=FakeScanner(INFECTED)
    )
    evidence = Evidence(
        case_id=sample_case.id,
        title="Evidencia rechazada",
        evidence_type="documento",
        status=str(EvidenceStatus.UPLOADED),
        created_by=admin_user.id,
        is_active=True,
    )
    database_session.add(evidence)
    await database_session.flush()

    _file, outcome = await service.attach_original(
        evidence, make_jpeg(), "mal.jpg", declared_mime="image/jpeg", actor=admin_user
    )

    assert not outcome.queued
    assert outcome.derivatives == 0
    assert "EICAR.Test.File-Test" in (outcome.detail or "")


async def test_an_unavailable_engine_fails_the_upload_closed(
    database_session: AsyncSession, sample_case: Case, admin_user: User, tmp_path: Path
) -> None:
    scanner = FakeScanner(AntivirusUnavailable("clamd no responde"))
    service = EvidenceService(
        database_session, storage=LocalStorage(tmp_path), scanner=scanner
    )
    evidence = Evidence(
        case_id=sample_case.id,
        title="Evidencia sin motor",
        evidence_type="documento",
        status=str(EvidenceStatus.UPLOADED),
        created_by=admin_user.id,
        is_active=True,
    )
    database_session.add(evidence)
    await database_session.flush()

    with pytest.raises(EvidenceError) as excinfo:
        await service.attach_original(
            evidence,
            make_jpeg(),
            "nose.jpg",
            declared_mime="image/jpeg",
            actor=admin_user,
        )

    assert "no disponible" in str(excinfo.value)
    # The in-flight copy goes too: an object whose attachment is refused must
    # not linger on disk after the failed request.
    file = (await database_session.execute(select(EvidenceFile))).scalars().one()
    assert (await service.storage.stat(file.storage_key)) is None


# --- Evidence: queued path ------------------------------------------------


async def test_a_queued_infected_upload_is_quarantined_by_the_worker(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.evidence.INLINE_LIMIT_BYTES", 10)
    service, evidence, _file = await _evidence_upload(
        database_session, sample_case, admin_user, FakeScanner(CLEAN), tmp_path
    )
    assert evidence.status == str(EvidenceStatus.PROCESSING)
    job = (
        (await database_session.execute(select(EvidenceProcessingJob))).scalars().one()
    )
    file = (
        (
            await database_session.execute(
                select(EvidenceFile).where(EvidenceFile.is_original.is_(True))
            )
        )
        .scalars()
        .one()
    )
    assert (await service.storage.stat(file.storage_key)) is not None, (
        "el original debería estar en disco antes del worker"
    )

    service.scanner = FakeScanner(INFECTED)
    outcome = await service.run_queued_job(job, worker="test")

    assert "EICAR" in (outcome.detail or "")
    refreshed_job = await database_session.get(EvidenceProcessingJob, job.id)
    refreshed_evidence = await database_session.get(Evidence, evidence.id)
    assert refreshed_job is not None and refreshed_evidence is not None
    assert refreshed_job.status == str(JobStatus.FAILED)
    assert refreshed_job.error is not None and "Antivirus" in refreshed_job.error
    assert refreshed_evidence.status == str(EvidenceStatus.QUARANTINED)
    assert (await service.storage.stat(file.storage_key)) is None


async def test_an_unavailable_engine_postpones_the_job_instead_of_failing_it(
    database_session: AsyncSession,
    sample_case: Case,
    admin_user: User,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.evidence.INLINE_LIMIT_BYTES", 10)
    service, evidence, _file = await _evidence_upload(
        database_session, sample_case, admin_user, FakeScanner(CLEAN), tmp_path
    )
    job = (
        (await database_session.execute(select(EvidenceProcessingJob))).scalars().one()
    )

    unavailable = AntivirusUnavailable("clamd abajo")
    service.scanner = FakeScanner(unavailable)
    with pytest.raises(AntivirusUnavailable):
        await service.run_queued_job(job, worker="test")

    refreshed = await database_session.get(EvidenceProcessingJob, job.id)
    assert refreshed is not None
    assert refreshed.status == str(JobStatus.RUNNING)
    assert refreshed.attempts == 1


# --- documents ------------------------------------------------------------


async def test_an_infected_document_version_is_never_recorded(
    database_session: AsyncSession,
    sample_document: Document,
    tmp_path: Path,
) -> None:
    storage = LocalStorage(tmp_path)
    service = DocumentService(
        database_session, storage=storage, scanner=FakeScanner(INFECTED)
    )

    with pytest.raises(DocumentError) as excinfo:
        await service.add_version(
            sample_document, make_jpeg(), "adjunto.jpg", declared_mime="image/jpeg"
        )

    assert "EICAR.Test.File-Test" in str(excinfo.value)
    versions = (
        (
            await database_session.execute(
                select(func.count()).select_from(DocumentVersion)
            )
        )
        .scalar_one()
    )
    assert versions == 0


async def test_an_unavailable_engine_closes_the_document_version(
    database_session: AsyncSession,
    sample_document: Document,
    tmp_path: Path,
) -> None:
    service = DocumentService(
        database_session,
        storage=LocalStorage(tmp_path),
        scanner=FakeScanner(AntivirusUnavailable("x")),
    )

    with pytest.raises(DocumentError) as excinfo:
        await service.add_version(sample_document, make_jpeg(), "adjunto.jpg")

    assert "no disponible" in str(excinfo.value)


async def test_a_clean_document_version_is_recorded(
    database_session: AsyncSession,
    sample_document: Document,
    tmp_path: Path,
) -> None:
    service = DocumentService(
        database_session, storage=LocalStorage(tmp_path), scanner=FakeScanner(CLEAN)
    )

    version = await service.add_version(sample_document, make_jpeg(), "adjunto.jpg")

    assert version.version_number == 1
