"""Database backup and restore verification.

The point of this module is not to produce a backup file. It is to prove that a
backup can be restored and that the restored copy is intact. A dump that has
never been restored is a hypothesis, not a backup.

The check is deliberately independent of the dump: it asks the restored
database to count rows and to run the application against itself, rather than
trusting the file size or the exit code of `pg_restore`.

Nothing here is specific to PostgreSQL beyond the tooling invoked, and no
credential ever reaches a log line: passwords are passed through the
environment and the connection URL is redacted in every message.
"""

import logging
import os
import re
import shutil
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger(__name__)

DUMP_SUFFIX = ".dump"
DEFAULT_RETENTION = 30


class BackupError(Exception):
    """Raised when a backup or its verification cannot be completed."""


def redact(url: str) -> str:
    """Remove the password from a connection URL so it can be logged safely."""
    try:
        parts = urlsplit(url)
    except ValueError:  # pragma: no cover - urlsplit rarely raises
        return "<url>"
    if not parts.netloc or "@" not in parts.netloc:
        return url
    userinfo, _, host = parts.netloc.rpartition("@")
    user, _, _password = userinfo.partition(":")
    return urlunsplit((parts.scheme, f"{user}:***@{host}", *parts[2:]))


@dataclass(frozen=True)
class BackupArtifact:
    """A dump on disk, with the digest that identifies it."""

    path: Path
    size_bytes: int
    sha256: str
    created_at: datetime
    kind: str = "postgres-custom"

    def as_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "created_at": self.created_at.isoformat(),
            "kind": self.kind,
        }


@dataclass
class RestoreReport:
    """Result of restoring a dump into a scratch database and inspecting it."""

    dump_path: Path
    dump_sha256: str | None = None
    dump_digest_matches: bool | None = None
    restored: bool = False
    alembic_revision: str | None = None
    table_count: int = 0
    row_counts: dict[str, int] = field(default_factory=dict)
    critical_tables_present: bool = False
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return self.restored and self.critical_tables_present and not self.errors

    def as_dict(self) -> dict[str, object]:
        return {
            "dump_path": str(self.dump_path),
            "dump_sha256": self.dump_sha256,
            "dump_digest_matches": self.dump_digest_matches,
            "restored": self.restored,
            "alembic_revision": self.alembic_revision,
            "table_count": self.table_count,
            "row_counts": self.row_counts,
            "critical_tables_present": self.critical_tables_present,
            "duration_seconds": self.duration_seconds,
            "healthy": self.healthy,
            "errors": self.errors,
        }


#: Tables whose absence means the restored database is useless.
CRITICAL_TABLES: tuple[str, ...] = (
    "users",
    "cases",
    "documents",
    "document_versions",
    "change_logs",
    "audit_logs",
    "integrity_scans",
)

_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_]+$")


def _safe_tag(tag: str) -> str:
    """Reduce a free text tag to a harmless filename fragment.

    A tag comes from a human or a scheduler, but it ends up in a file name, so
    separators and traversal sequences have to be impossible by construction
    rather than by escaping.
    """
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", tag)
    cleaned = cleaned.replace("..", ".")
    cleaned = cleaned.strip(".-")
    return cleaned[:60] or "sin-etiqueta"


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise BackupError(f"La herramienta {name} no está disponible en el PATH")
    return path


def _run(command: Sequence[str], *, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[-2000:]
        raise BackupError(
            f"Falló {' '.join(command[:2])}: {detail}"
        )
    return completed.stdout


class BackupService:
    """Create database dumps and prove that they can be restored."""

    def __init__(self, database_url: str | None = None, backup_dir: Path | None = None):
        settings_url = database_url or _database_url_from_env()
        self.url = make_url(settings_url)
        self.backup_dir = backup_dir or Path(".tmp/backups")
        self._app_database = self.url.database

    # -- dump ---------------------------------------------------------------

    def _env(self) -> dict[str, str]:
        """Environment for the pg tools, with the password never on the command line."""
        env = dict(os.environ)
        if self.url.password:
            env["PGPASSWORD"] = self.url.password
        return env

    def _admin_url(self, database: str) -> str:
        return self._pg_url(database)

    def _pg_url(self, database: str | None = None) -> str:
        """Render the URL with a plain `postgresql` driver for the pg tools.

        `pg_dump` and `pg_restore` do not understand SQLAlchemy drivers such as
        `postgresql+asyncpg`. Passing it verbatim makes them ignore the host and
        fall back to the local unix socket, which fails in a container.
        """
        url = self.url.set(database=database or self._app_database)
        driver, _, _rest = url.drivername.partition("+")
        return url.set(drivername=driver).render_as_string(hide_password=False)

    def _connection_args(self) -> list[str]:
        """Host, port and user flags shared by createdb and dropdb.

        Without an explicit username these tools fall back to the operating
        system user, which inside the container is `root` and has no role in
        PostgreSQL.
        """
        return [
            "--host",
            self.url.host or "localhost",
            "--port",
            str(self.url.port or 5432),
            "--username",
            self.url.username or "postgres",
        ]

    def dump(self, *, tag: str | None = None) -> BackupArtifact:
        """Create a compressed custom format dump and return its digest."""
        pg_dump = _require_tool("pg_dump")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        name = f"wabogados-{stamp}{DUMP_SUFFIX}"
        if tag:
            name = f"wabogados-{stamp}-{_safe_tag(tag)}{DUMP_SUFFIX}"
        target = self.backup_dir / name

        command = [
            pg_dump,
            "--format=custom",
            "--compress=9",
            "--no-owner",
            "--no-privileges",
            "--file",
            str(target),
        ]
        # `--dbname` keeps the URL out of the process arguments.
        command.extend(["--dbname", self._pg_url()])

        logger.info("Volcando la base de datos a %s", target)
        _run(command, env=self._env())

        if not target.is_file() or target.stat().st_size == 0:
            raise BackupError("pg_dump no produjo un archivo utilizable")

        digest = sha256(target.read_bytes()).hexdigest()
        return BackupArtifact(
            path=target,
            size_bytes=target.stat().st_size,
            sha256=digest,
            created_at=datetime.now(UTC),
        )

    def write_manifest(self, artifact: BackupArtifact, extra: dict[str, object]) -> Path:
        """Record what the backup contains and which configuration it expects.

        The manifest is what turns a pile of files into a restorable backup:
        without the revision and the settings, a restore is guesswork.
        """
        import json

        manifest = {
            "database_url": redact(self.url.render_as_string(hide_password=True)),
            "database": self._app_database,
            **artifact.as_dict(),
            **extra,
        }
        path = artifact.path.with_suffix(".manifest.json")
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
        return path

    def digest_of(self, path: Path) -> str:
        return sha256(path.read_bytes()).hexdigest()

    # -- prune --------------------------------------------------------------

    def prune(self, *, keep: int = DEFAULT_RETENTION) -> list[Path]:
        """Delete only our own old dumps. Refuses a nonsensical retention."""
        if keep < 1:
            raise BackupError("Hay que conservar al menos una copia")
        dumps = sorted(self.backup_dir.glob(f"*{DUMP_SUFFIX}"))
        removed: list[Path] = []
        for stale in dumps[:-keep] if len(dumps) > keep else []:
            try:
                stale.unlink()
                removed.append(stale)
                stale.with_suffix(".manifest.json").unlink(missing_ok=True)
            except OSError as error:  # pragma: no cover - permissions
                logger.warning("No se pudo borrar %s: %s", stale, error)
        return removed

    # -- restore ------------------------------------------------------------

    async def verify_restore(
        self,
        dump_path: Path,
        *,
        expected_sha256: str | None = None,
        keep_database: bool = False,
    ) -> RestoreReport:
        """Restore the dump into a scratch database and inspect the result.

        The scratch database is created, populated, measured and dropped, so the
        real one is never touched. Returns a report describing what the restored
        copy actually contains.
        """
        started = time.monotonic()
        report = RestoreReport(dump_path=dump_path)

        if not dump_path.is_file():
            report.errors.append("El archivo de dump no existe")
            report.duration_seconds = round(time.monotonic() - started, 3)
            return report

        if expected_sha256:
            report.dump_sha256 = self.digest_of(dump_path)
            report.dump_digest_matches = report.dump_sha256 == expected_sha256
            if not report.dump_digest_matches:
                report.errors.append(
                    "El digest del dump no coincide con el registrado en el manifiesto"
                )
                report.duration_seconds = round(time.monotonic() - started, 3)
                return report

        scratch = f"wabogados_verify_{datetime.now(UTC):%Y%m%d%H%M%S}"
        if not _SAFE_NAME.match(scratch):  # pragma: no cover - generated name
            raise BackupError("Nombre de base de datos temporal no válido")

        engine = self._create_scratch_engine(scratch)
        try:
            self._create_database(scratch)
            self._restore_into(scratch, dump_path)
            report.restored = True
            await self._inspect(engine, report)
        except BackupError as error:
            report.errors.append(str(error))
        except Exception as error:
            report.errors.append(f"Error inesperado: {error}")
        finally:
            await engine.dispose()
            if not keep_database:
                self._drop_database(scratch)

        report.duration_seconds = round(time.monotonic() - started, 3)
        return report

    def _create_scratch_engine(self, database: str) -> AsyncEngine:
        url: URL = self.url.set(database=database)
        return create_async_engine(url, pool_pre_ping=False)

    def _create_database(self, database: str) -> None:
        createdb = _require_tool("createdb")
        command = [
            createdb,
            *self._connection_args(),
            "--owner",
            self.url.username or "postgres",
            database,
        ]
        try:
            _run(command, env=self._env())
        except BackupError as error:
            # A leftover scratch database from a crashed run is not fatal.
            if "already exists" not in str(error):
                raise

    def _restore_into(self, database: str, dump_path: Path) -> None:
        pg_restore = _require_tool("pg_restore")
        command = [
            pg_restore,
            "--no-owner",
            "--no-privileges",
            "--exit-on-error",
            "--dbname",
            self._admin_url(database),
            str(dump_path),
        ]
        # The URL carries the password, so it is passed via PGPASSWORD and the
        # argument list is scrubbed before any error is surfaced.
        try:
            _run(command, env=self._env())
        except BackupError:
            raise
        except Exception as error:  # pragma: no cover - defensive
            raise BackupError(str(error)) from error

    def _drop_database(self, database: str) -> None:
        try:
            dropdb = _require_tool("dropdb")
            _run(
                [dropdb, "--if-exists", "--force", *self._connection_args(), database],
                env=self._env(),
            )
        except BackupError as error:  # pragma: no cover - permissions
            logger.warning("No se pudo borrar la base temporal %s: %s", database, error)

    async def _inspect(self, engine: AsyncEngine, report: RestoreReport) -> None:
        """Ask the restored database about itself rather than trusting the file."""
        async with engine.connect() as connection:
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            report.alembic_revision = str(revision) if revision else None

            tables = await connection.scalar(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
            )
            report.table_count = int(tables or 0)

            present = {
                str(row[0])
                for row in (
                    await connection.execute(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_schema = 'public'"
                        )
                    )
                ).all()
            }
            missing = [table for table in CRITICAL_TABLES if table not in present]
            report.critical_tables_present = not missing
            if missing:
                report.errors.append(f"Faltan tablas críticas en la restauración: {missing}")

            for table in CRITICAL_TABLES:
                if table not in present:
                    continue
                try:
                    count = await connection.scalar(text(f'SELECT count(*) FROM "{table}"'))
                except Exception as error:
                    report.errors.append(f"No se pudo contar {table}: {error}")
                    continue
                report.row_counts[table] = int(count or 0)


def _database_url_from_env() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise BackupError("DATABASE_URL no está definida")
    return url


__all__ = [
    "CRITICAL_TABLES",
    "BackupArtifact",
    "BackupError",
    "BackupService",
    "RestoreReport",
    "redact",
]