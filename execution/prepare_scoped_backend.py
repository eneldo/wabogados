#!/usr/bin/env python3
"""Prepare a clean Git baseline plus explicitly reviewed backend paths, without editing the worktree.

Use when unrelated, unvalidated work must not be deployed with an additive feature.
This only prepares a disposable build context; it does not build, migrate or deploy.
"""

import argparse
import hashlib
import io
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    paths = sorted(set(args.paths))
    for name in paths:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            parser.error(f"Use una ruta relativa sin '..': {name}")
        source = (ROOT / name).resolve()
        if not source.is_relative_to(ROOT / "backend") or not source.is_file():
            parser.error(f"Solo se admiten archivos existentes dentro de backend/: {name}")
    commit = subprocess.check_output(["git", "rev-parse", args.base], cwd=ROOT, text=True).strip()
    archive = subprocess.check_output(["git", "archive", commit, "backend"], cwd=ROOT)
    (ROOT / ".tmp").mkdir(exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix="scoped-backend-", dir=ROOT / ".tmp"))
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(target, filter="data")
    manifest = {"base": commit, "files": {}}
    for name in paths:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
        manifest["files"][name] = hashlib.sha256(destination.read_bytes()).hexdigest()
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(target / "backend")


if __name__ == "__main__":
    main()
