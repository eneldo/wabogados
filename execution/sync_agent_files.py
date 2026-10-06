#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MASTER_FILE = ROOT / ".agent" / "MASTER_AGENT.md"
TARGET_FILES = [ROOT / "AGENTS.md", ROOT / "CLAUDE.md", ROOT / "GEMINI.md"]

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")

def validate_master() -> None:
    if not MASTER_FILE.is_file():
        print(f"[ERROR] No existe {MASTER_FILE.relative_to(ROOT)}")
        sys.exit(2)

def check_sync(show_hashes: bool = False) -> bool:
    validate_master()
    master = read_text(MASTER_FILE)
    ok = True
    print("\n=== Verificación de archivos del agente ===\n")
    for target in TARGET_FILES:
        same = target.is_file() and read_text(target) == master
        print(f"[{'OK' if same else 'DIFF'}] {target.relative_to(ROOT)}")
        if show_hashes and target.exists():
            print(f"       SHA256: {sha256_file(target)}")
        ok = ok and same
    if show_hashes:
        print(f"\nMASTER SHA256: {sha256_file(MASTER_FILE)}")
    return ok

def synchronize() -> None:
    validate_master()
    master = read_text(MASTER_FILE)
    for target in TARGET_FILES:
        if target.is_file():
            try:
                if read_text(target) == master:
                    print(f"[OK]      {target.relative_to(ROOT)}")
                    continue
            except UnicodeDecodeError:
                pass
        write_text(target, master)
        print(f"[UPDATED] {target.relative_to(ROOT)}")

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    p.add_argument("--hashes", action="store_true")
    args = p.parse_args()
    if args.check:
        sys.exit(0 if check_sync(args.hashes) else 1)
    synchronize()
    if not check_sync(args.hashes):
        sys.exit(1)

if __name__ == "__main__":
    main()
