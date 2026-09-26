import os
from pathlib import Path
import sys
import time
import pytest

from amd_nr.errors import ContractError, ProcessError, ResourceError, RunCancelled, RunTimeout
from amd_nr.process import run_process


def execute(tmp_path, code, **kwargs):
    return run_process([sys.executable, '-c', code], cwd=tmp_path, log=tmp_path / 'run.log',
                       timeout=kwargs.pop('timeout', 5), **kwargs)


def test_process_exit_and_child_only_environment(tmp_path):
    execute(tmp_path, 'import os;print(os.environ["AMD_NR_TEST_ENV"])', env_overrides={'AMD_NR_TEST_ENV': 'child value'})
    assert (tmp_path / 'run.log').read_text().strip() == 'child value'
    assert os.environ.get('AMD_NR_TEST_ENV') is None


def test_nonzero_exit(tmp_path):
    with pytest.raises(ProcessError):
        execute(tmp_path, 'raise SystemExit(7)')


def test_timeout(tmp_path):
    with pytest.raises(RunTimeout):
        execute(tmp_path, 'import time;time.sleep(15)', timeout=.15)


def test_log_limit(tmp_path):
    with pytest.raises(ResourceError):
        execute(tmp_path, 'print("x"*10000)', max_log_bytes=100)


@pytest.mark.parametrize('timeout', [0, -1, True, float('nan'), float('inf')])
def test_invalid_timeout(tmp_path, timeout):
    with pytest.raises(ContractError):
        execute(tmp_path, 'pass', timeout=timeout)


def test_no_shell_interpolation(tmp_path):
    value = 'space 日本語 ; $(touch PWNED) & echo x'
    run_process([sys.executable, '-c', 'import sys;print(sys.argv[1])', value], cwd=tmp_path,
                log=tmp_path / 'log.txt', timeout=5)
    assert (tmp_path / 'log.txt').read_text().strip() == value
    assert not (tmp_path / 'PWNED').exists()


def test_cancel_before_launch(tmp_path):
    def cancel(): raise RunCancelled('test')
    with pytest.raises(RunCancelled):
        execute(tmp_path, 'print("not reached")', cancel=cancel)
    assert not (tmp_path / 'run.log').exists()


@pytest.mark.skipif(os.name == 'nt', reason='POSIX process-group assertion; Windows needs hardware/Job Object testing')
def test_exited_parent_does_not_leave_live_child(tmp_path):
    child_code = 'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(30)'
    code = ('import subprocess,sys,pathlib;'
            f'p=subprocess.Popen([sys.executable,"-c",{child_code!r}]);'
            'pathlib.Path("child.pid").write_text(str(p.pid));raise SystemExit(4)')
    with pytest.raises(ProcessError):
        execute(tmp_path, code)
    pid = int((tmp_path / 'child.pid').read_text())
    for _ in range(40):
        path = Path(f'/proc/{pid}/stat')
        if not path.exists() or path.read_text().split()[2] == 'Z':
            break
        time.sleep(.025)
    else:
        os.kill(pid, 9)
        pytest.fail('Child process survived failed coordinator cleanup')
