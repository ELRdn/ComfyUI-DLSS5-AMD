#!/usr/bin/env python3
"""Verify the delivered file inventory, offline. Generated local extras ignored."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    manifest = json.loads((ROOT / 'PACKAGE_MANIFEST.json').read_text(encoding='utf-8'))
    failures = []
    for entry in manifest['files']:
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:
            failures.append(str(relative)); continue
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            failures.append(str(relative)); continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry['sha256'] or path.stat().st_size != entry['bytes']:
            failures.append(str(relative))
    print(json.dumps({'status': 'failed' if failures else 'passed', 'files_checked': len(manifest['files']),
        'mismatches': failures, 'note': 'Integrity versus local inventory, not signed publisher authenticity.'}, indent=2))
    return int(bool(failures))

if __name__ == '__main__':
    raise SystemExit(main())
