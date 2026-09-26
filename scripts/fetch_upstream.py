#!/usr/bin/env python3
"""Explicitly fetch only the inspected MIT native HOST source. No weights/DLLs.

This command uses the network only when the user runs it. It never runs fetched
code. Review the fetched source and license before invoking build_native.ps1.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def git_blob_id(payload: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(payload)).encode('ascii') + b'\0' + payload).hexdigest()


def run_git(args: list[str], directory: Path) -> str:
    env = os.environ.copy()
    env['GIT_TERMINAL_PROMPT'] = '0'
    return subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'core.hooksPath=', *args],
        cwd=directory, env=env, stdin=subprocess.DEVNULL, text=True, capture_output=True,
        check=True, timeout=180).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=ROOT / 'third_party' / 'DLSS5-AMD-Video')
    parser.add_argument('--verify-only', action='store_true', help='No network or writes; verify an existing checkout')
    args = parser.parse_args()
    lock = json.loads((ROOT / 'upstream.lock.json').read_text())
    dest = args.destination.resolve()
    try:
        if not args.verify_only:
            if dest.exists():
                raise FileExistsError('Destination exists. Use --verify-only or choose a fresh directory; never reset user work.')
            dest.mkdir(parents=True)
            run_git(['init'], dest)
            run_git(['remote', 'add', 'origin', lock['repository']], dest)
            run_git(['fetch', '--depth', '1', 'origin', lock['commit']], dest)
            run_git(['checkout', '--detach', 'FETCH_HEAD'], dest)
        if run_git(['rev-parse', 'HEAD'], dest) != lock['commit']:
            raise ValueError('Unexpected checkout commit.')
        if run_git(['status', '--porcelain'], dest):
            raise ValueError('Checkout contains changes or untracked files. Review them before building.')
        if run_git(['remote', 'get-url', 'origin'], dest) != lock['repository']:
            raise ValueError('Unexpected origin URL.')
        for name, digest in lock['git_blobs'].items():
            path = dest / name
            if path.is_symlink() or git_blob_id(path.read_bytes()) != digest:
                raise ValueError(f'Inspected source hash mismatch: {name}')
        print(json.dumps({'status': 'verified_source_only', 'commit': lock['commit'],
            'path': str(dest), 'gpu_tested': False, 'weights_or_runtime_downloaded': False}, indent=2))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        if isinstance(exc, subprocess.CalledProcessError):
            print(exc.stderr, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
