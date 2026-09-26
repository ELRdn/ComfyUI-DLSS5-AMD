#!/usr/bin/env python3
"""Run CPU/contract tests and store auditable evidence; never claim GPU coverage."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    evidence = ROOT / 'evidence'
    evidence.mkdir(exist_ok=True)
    cmd = [sys.executable, '-m', 'coverage', 'run', '-m', 'pytest', '-q',
           '--junitxml=evidence/junit.xml']
    with (evidence / 'pytest.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=180)
    for args in [['json', '-o', 'evidence/coverage.json'], ['report']]:
        with (evidence / ('coverage-summary.txt' if args == ['report'] else 'coverage-command.txt')).open('w') as log:
            subprocess.run([sys.executable, '-m', 'coverage', *args], cwd=ROOT, stdout=log,
                           stderr=subprocess.STDOUT, timeout=30, check=True)
    subprocess.run([sys.executable, '-m', 'amd_nr', 'doctor', '--output', 'evidence/environment.json'],
                   cwd=ROOT, stdout=subprocess.DEVNULL, timeout=30, check=True)
    suites = ET.parse(evidence / 'junit.xml').getroot().findall('testsuite')
    totals = {key: sum(int(s.get(key, 0)) for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')}
    summary = {'schema': 1, 'collected_utc': datetime.now(timezone.utc).isoformat(),
        'exit_code': result.returncode, **totals,
        'native_gpu_inference': 'NOT_RUN', 'windows_native_build': 'NOT_RUN',
        'full_comfyui_server_browser': 'NOT_RUN',
        'tested': ['CPU Python logic', 'Comfy node methods and package import',
                   'external native contract with explicitly labelled test double',
                   'real FFmpeg lossless video/audio roundtrip'],
        'note': 'Coverage and fake-engine completion are NOT evidence of real DLSS execution.'}
    (evidence / 'test-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
    return result.returncode

if __name__ == '__main__':
    raise SystemExit(main())
