"""Antivirus engine for uploads: minimal ClamAV client.

Firm decision (2026-10-21) for the pending question in KNOWN_ISSUES.md:

- **Where the content is analyzed**: in a `clamav` container on the same stack,
  reached via the INSTREAM protocol of clamd. No extra Python dependency: the
  protocol is a length-prefixed chunked write plus one response line.
- **What to do when an infected file is found**: discard the stored copy,
  mark the record and leave the verdict in the custody trail (evidence) or in
  the refusal of the version (documents).
- **What to do when the engine does not answer**: fail closed. `'fail open'
  would guarantee this gate never worked without anybody learning about it.

Structural validation (signatures, MIME, dimension) is complementary: it stops
disguised executables, malicious MIME mismatches and decompression bombs, while
this engine looks into the payload.

The engine is configured through `antivirus_host`. `None` disables the scan —
documented loudly, not hidden: without a host there simply is no engine and
nothing pretends otherwise.
"""

import asyncio
import logging
import struct
from dataclasses import dataclass

from app.core.config import Settings

logger = logging.getLogger(__name__)

#: ClamAV command that asks clamd to scan a stream sent right after it.
_INSTREAM = b"zINSTREAM\x00"

#: Bytes per chunk. Everything smaller keeps the request to one write.
_CHUNK = 65536


class AntivirusError(Exception):
    """Base class for the antivirus engine failures."""


class AntivirusUnavailable(AntivirusError):
    """The engine cannot be reached or did not answer a parseable verdict.

    Raised instead of returning a verdict: an answer we cannot interpret is
    `engine down until proven otherwise`, and every caller treats it as
    `fail closed` (reject or postpone, never accept quietly).
    """


@dataclass(frozen=True)
class ScanResult:
    """What clamd answered for one uploaded payload."""

    #: True only when the verdict is literally `OK`.
    clean: bool
    #: Detection name from clamd, e.g. `EICAR.Test.File-Test`. None when clean.
    signature: str | None
    #: The raw response line, for the custody trail.
    detail: str


class Scanner:
    """What the storage pipeline needs from an engine."""

    async def scan(self, content: bytes) -> ScanResult:
        """Return the verdict of one payload, or raise AntivirusUnknown."""
        raise NotImplementedError


class ClamavScanner(Scanner):
    """Client of one clamd endpoint via the INSTREAM protocol."""

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout

    async def scan(self, content: bytes) -> ScanResult:
        try:
            response = await asyncio.wait_for(self._exchange(content), self.timeout)
        except (TimeoutError, OSError, ConnectionError) as error:
            raise AntivirusUnavailable(str(error) or type(error).__name__) from error

        text = response.decode("ascii", "replace").strip().rstrip("\x00")
        return _interpret(text)

    async def _exchange(self, content: bytes) -> bytes:
        reader, writer = await asyncio.open_connection(self.host, self.port)
        try:
            writer.write(_INSTREAM)
            view = memoryview(content)
            for offset in range(0, len(content), _CHUNK):
                chunk = view[offset : offset + _CHUNK]
                writer.write(struct.pack(">I", len(chunk)))
                writer.write(chunk)
            # Empty chunk: end of stream. clamd answers after the last one.
            writer.write(struct.pack(">I", 0))
            await writer.drain()
            return await reader.read(4096)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, ConnectionError):
                pass


def _interpret(text: str) -> ScanResult:
    """Turn one clamd answer line into a verdict.

    clamd answers `stream: OK` for clean content and `stream: <signature> FOUND`
    for detections. Anything else (empty, error, unknown wording) cannot be a
    verdict, so it is an engine failure rather than an implicit clean.
    """
    if text.endswith("OK"):
        return ScanResult(clean=True, signature=None, detail=text)
    if " FOUND" in text:
        signature = text.rsplit(" FOUND", 1)[0].split(":")[-1].strip()
        return ScanResult(clean=False, signature=signature, detail=text)
    raise AntivirusUnavailable(f"Respuesta no interpretada del antivirus: {text!r}")


def build_scanner(settings: Settings) -> Scanner | None:
    """Return the configured engine, or None when none is configured.

    A `None` here is a policy, not an error: the env var was never set, which in
    this codebase happens deliberately in tests and in any deployment where the
    firm has not contracted or deployed an engine.
    """
    if settings.antivirus_host is None:
        return None
    logger.info(
        "Antivirus activo: clamd en %s:%d",
        settings.antivirus_host,
        settings.antivirus_port,
    )
    return ClamavScanner(
        settings.antivirus_host, settings.antivirus_port, settings.antivirus_timeout_seconds
    )
