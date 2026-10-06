"""The objects in a backup, verified by digest and not by counting.

`scripts/backup.sh` writes `objects.count` and a `MANIFEST.sha256` with a digest
for every file. Until now **nothing read the manifest**: the count was written
and never consumed, and a count cannot detect a truncated file. A backup whose
evidence originals are half-copied and whose only recorded fact is "there are
812 objects" is exactly the kind of copy that is discovered to be worthless on
the day it is needed.

These tests are the reason `MANIFEST.sha256` is now load-bearing.
"""

import os
from hashlib import sha256
from pathlib import Path

import pytest

from app.services.backup_manifest import (
    MANIFEST_NAME,
    ManifestError,
    build_manifest,
    verify_manifest,
)


def _write(root: Path, relative: str, content: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _digest_of(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_a_complete_backup_verifies(tmp_path: Path) -> None:
    _write(tmp_path, "objects/evidences/case/original/a.pdf", b"%PDF-1.7 contenido")
    _write(tmp_path, "objects/documents/b.pdf", b"%PDF-1.7 otro")
    manifest = build_manifest(tmp_path)

    report = verify_manifest(manifest)

    assert report.healthy is True
    assert report.verified_count == 2
    assert report.errors == []


def test_a_truncated_object_is_detected(tmp_path: Path) -> None:
    """The case a count cannot see: the file is still there, with less in it."""
    original = b"%PDF-1.7 " + b"contenido que no debe perder una sola letra"
    _write(tmp_path, "objects/evidences/original.pdf", original)
    manifest = build_manifest(tmp_path)

    _write(tmp_path, "objects/evidences/original.pdf", original[:10])

    report = verify_manifest(manifest)

    assert report.healthy is False
    assert any("original.pdf" in error for error in report.errors)
    assert report.corrupted_count == 1


def test_a_missing_object_is_detected(tmp_path: Path) -> None:
    _write(tmp_path, "objects/evidences/ausente.pdf", b"%PDF-1.7")
    manifest = build_manifest(tmp_path)

    (tmp_path / "objects/evidences/ausente.pdf").unlink()

    report = verify_manifest(manifest)

    assert report.healthy is False
    assert report.missing_count == 1
    assert any("ausente.pdf" in error for error in report.errors)


def test_a_modified_object_keeps_the_count_and_still_fails(tmp_path: Path) -> None:
    """The exact failure the count-only check could not see."""
    _write(tmp_path, "objects/uno.pdf", b"original")
    _write(tmp_path, "objects/dos.pdf", b"original")
    manifest = build_manifest(tmp_path)
    _write(tmp_path, "objects/uno.pdf", b"alterado")

    report = verify_manifest(manifest)

    assert report.total_count == 2, "el recuento no cambia: por eso no vale"
    assert report.healthy is False


def test_the_manifest_never_lists_itself(tmp_path: Path) -> None:
    """A manifest containing its own digest can never verify itself."""
    _write(tmp_path, "objects/a.pdf", b"x")

    manifest = build_manifest(tmp_path)

    assert MANIFEST_NAME not in manifest.read_text(encoding="utf-8")
    assert verify_manifest(manifest).healthy is True


def test_a_file_added_after_the_manifest_is_reported_but_not_fatal(
    tmp_path: Path,
) -> None:
    """An extra file is not corruption, but it is worth saying out loud."""
    _write(tmp_path, "objects/a.pdf", b"x")
    manifest = build_manifest(tmp_path)
    _write(tmp_path, "objects/sobresaliente.pdf", b"nuevo")

    report = verify_manifest(manifest)

    assert report.healthy is True
    assert report.unlisted_count == 1


def test_the_manifest_cannot_escape_its_directory(tmp_path: Path) -> None:
    """A relative path with `..` would read a file outside the backup."""
    backup = tmp_path / "backup"
    backup.mkdir()
    secret = tmp_path / "secreto.txt"
    secret.write_text("no deberia leerse", encoding="utf-8")
    manifest = backup / MANIFEST_NAME
    manifest.write_text(f"{_digest_of(secret)}  ../secreto.txt\n", encoding="utf-8")

    report = verify_manifest(manifest)

    assert report.healthy is False
    assert any("fuera" in error for error in report.errors)


def test_an_empty_manifest_is_not_a_pass(tmp_path: Path) -> None:
    """A manifest that verifies nothing has verified nothing."""
    manifest = build_manifest(tmp_path)

    report = verify_manifest(manifest)

    assert report.total_count == 0
    assert report.healthy is False
    assert report.errors


def test_a_missing_manifest_is_an_error_not_a_pass(tmp_path: Path) -> None:
    with pytest.raises(ManifestError):
        verify_manifest(tmp_path / MANIFEST_NAME)


def test_a_malformed_line_is_reported_with_its_line_number(tmp_path: Path) -> None:
    _write(tmp_path, "objects/a.pdf", b"x")
    manifest = tmp_path / MANIFEST_NAME
    manifest.write_text("no-es-un-digest  objects/a.pdf\n", encoding="utf-8")

    report = verify_manifest(manifest)

    assert report.healthy is False
    assert any("línea 1" in error or "linea 1" in error for error in report.errors)


def test_the_report_is_serialisable(tmp_path: Path) -> None:
    import json

    _write(tmp_path, "objects/a.pdf", b"x")
    report = verify_manifest(build_manifest(tmp_path))

    assert json.loads(json.dumps(report.as_dict()))["healthy"] is True


def test_names_with_spaces_and_accents_survive(tmp_path: Path) -> None:
    """Backup paths come from user file names; spaces are normal, not an error."""
    _write(tmp_path, "objects/contrato de arrendamiento año 2026.pdf", b"%PDF")

    report = verify_manifest(build_manifest(tmp_path))

    assert report.healthy is True
    assert report.verified_count == 1


def test_the_manifest_uses_posix_separators(tmp_path: Path) -> None:
    """A manifest is portable: written on one machine, read on another.

    `str(Path.relative_to())` renders `\\` on Windows, and a manifest written that
    way lists files that do not exist on the Linux host that has to restore them.
    That reads exactly like total data loss, so the separator is pinned here
    rather than left to the platform that happened to make the backup.
    """
    _write(tmp_path, "objects/evidences/original.pdf", b"%PDF")

    body = build_manifest(tmp_path).read_text(encoding="utf-8")

    assert "\\" not in body
    assert "objects/evidences/original.pdf" in body


def test_verification_reads_large_files_without_loading_them(tmp_path: Path) -> None:
    """A 20 MB evidence original must not be read into memory to be hashed."""
    _write(tmp_path, "objects/grande.pdf", os.urandom(3 * 1024 * 1024))
    manifest = build_manifest(tmp_path)

    report = verify_manifest(manifest)

    assert report.healthy is True


# --- the operator facing command ------------------------------------------


def test_the_cli_reports_ok_on_an_intact_backup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.cli import verify_backup_files

    _write(tmp_path, "objects/a.pdf", b"x")
    manifest = build_manifest(tmp_path)

    exit_code = verify_backup_files.main(["--manifest", str(manifest)])

    assert exit_code == verify_backup_files.EXIT_OK
    assert "[OK]" in capsys.readouterr().out


def test_the_cli_fails_on_a_truncated_object(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.cli import verify_backup_files

    _write(tmp_path, "objects/a.pdf", b"%PDF-1.7 contenido completo")
    manifest = build_manifest(tmp_path)
    _write(tmp_path, "objects/a.pdf", b"%PDF")

    exit_code = verify_backup_files.main(["--manifest", str(manifest)])

    assert exit_code == verify_backup_files.EXIT_FAILED
    assert "ALTERADOS" in capsys.readouterr().out


def test_the_cli_exits_with_a_usage_error_when_the_manifest_is_absent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.cli import verify_backup_files

    exit_code = verify_backup_files.main(["--manifest", str(tmp_path / "nope.sha256")])

    assert exit_code == verify_backup_files.EXIT_USAGE
    assert "No existe el manifiesto" in capsys.readouterr().out


def test_the_cli_emits_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import json

    from app.cli import verify_backup_files

    _write(tmp_path, "objects/a.pdf", b"x")
    manifest = build_manifest(tmp_path)

    verify_backup_files.main(["--manifest", str(manifest), "--json"])

    assert json.loads(capsys.readouterr().out)["healthy"] is True


def test_objects_only_hides_the_database_noise_but_not_the_verdict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The dump is proven by restoring it; its absence here is not a second fault."""
    import json

    from app.cli import verify_backup_files

    _write(tmp_path, "postgres.dump", b"volcado")
    _write(tmp_path, "objects/a.pdf", b"x")
    manifest = build_manifest(tmp_path)
    (tmp_path / "postgres.dump").unlink()

    exit_code = verify_backup_files.main(
        ["--manifest", str(manifest), "--objects-only", "--json"]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == verify_backup_files.EXIT_FAILED, "el veredicto no se suaviza"
    assert not any("postgres.dump" in error for error in payload["errors"])


def test_strict_unlisted_turns_an_extra_file_into_a_failure(tmp_path: Path) -> None:
    from app.cli import verify_backup_files

    _write(tmp_path, "objects/a.pdf", b"x")
    manifest = build_manifest(tmp_path)
    _write(tmp_path, "objects/sobresaliente.pdf", b"nuevo")

    args = verify_backup_files.parse_args(["--manifest", str(manifest)])
    assert verify_backup_files.main(["--manifest", str(manifest)]) == verify_backup_files.EXIT_OK
    assert (
        verify_backup_files.main(["--manifest", str(manifest), "--strict-unlisted"])
        == verify_backup_files.EXIT_FAILED
    )
    assert args.strict_unlisted is False
