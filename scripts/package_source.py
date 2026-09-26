#!/usr/bin/env python3
"""Package only allowlisted source/docs/evidence; never include local runtime assets.

Review any private edits before public redistribution. This is not a secret scanner.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_NAMES = {
    '__init__.py', '.gitignore', '.gitattributes', 'pyproject.toml', 'requirements.txt', 'upstream.lock.json',
    'README.md', 'README.jp.md', 'REPORT_ja.md', 'REPORT.html', 'ROADMAP.md', 'DELIVERY.md', 'LICENSE',
    'SECURITY.md', 'THIRD_PARTY_NOTICES.md', 'CHANGELOG.md'}
EVIDENCE_NAMES = {'test-summary.json', 'junit.xml', 'pytest.log', 'coverage.json',
    'coverage-summary.txt', 'coverage-command.txt', 'environment.json', 'tool-versions.json',
    'report-validation.json', 'packaging-checks.json'}
RULES = {'amd_nr': {'.py'}, 'tests': {'.py'}, 'scripts': {'.py', '.ps1'},
         'docs': {'.md'}, 'workflows': {'.json'}}


def allowed(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    if '__pycache__' in relative.parts or path.is_symlink() or not path.is_file(): return False
    if len(relative.parts) == 1: return path.name in ROOT_NAMES
    if relative.parts[0] == 'config': return str(relative.as_posix()) == 'config/backend.example.json'
    if relative.parts[0] == 'evidence': return len(relative.parts) == 2 and path.name in EVIDENCE_NAMES
    return relative.parts[0] in RULES and path.suffix in RULES[relative.parts[0]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT.parent / 'ComfyUI-DLSS5-AMD-v0.1.0a1.zip')
    args = parser.parse_args()
    target = args.output.resolve()
    if target.exists(): raise FileExistsError('Choose a new archive path; existing deliverables are not overwritten.')
    files = sorted((p for p in ROOT.rglob('*') if allowed(p)), key=lambda p: p.relative_to(ROOT).as_posix())
    inventory = {'schema': 1, 'version': '0.1.0a1', 'hash_algorithm': 'SHA256',
        'self_excluded': 'PACKAGE_MANIFEST.json is not self-hashed',
        'note': 'File integrity inventory, not cryptographic publisher authentication.',
        'files': [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size,
                   'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
    manifest = ROOT / 'PACKAGE_MANIFEST.json'
    manifest.write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for path in files + [manifest]:
            # Stable ZIP metadata, independent of local permissions and file mtimes.
            entry = zipfile.ZipInfo(ROOT.name + '/' + path.relative_to(ROOT).as_posix(), date_time=(2026,9,25,0,0,0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            z.writestr(entry, path.read_bytes())
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(target.suffix + '.sha256').write_text(f'{digest}  {target.name}\n', encoding='ascii')
    print(json.dumps({'archive': str(target), 'sha256': digest, 'files': len(files) + 1,
                      'bytes': target.stat().st_size, 'external_runtime_included': False}, indent=2))


if __name__ == '__main__':
    main()
