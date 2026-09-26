"""Bounded, shell-free child processes, with process-tree cancellation."""
from __future__ import annotations

import math
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Callable, Mapping

from .errors import ContractError, ProcessError, ResourceError, RunTimeout

CancelCheck = Callable[[], None]


def stop_process_tree(process: subprocess.Popen) -> None:
    # On POSIX the process group may outlive its leader. Still stop descendants
    # after a failed coordinator exits. A Windows native coordinator owns a Job.
    if os.name == "nt" and process.poll() is not None:
        return
    if os.name == "nt":
        # Native coordinator additionally owns its own kill-on-close Job Object.
        killer = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
        try:
            subprocess.run([str(killer), "/PID", str(process.pid), "/T", "/F"],
                           stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=10, check=False,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired):
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=5)
    if os.name != "nt":
        # A grandchild can ignore TERM even after its parent exits successfully.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def run_process(argv: list[str], *, cwd: Path, log: Path, timeout: float,
                cancel: CancelCheck | None = None,
                env_overrides: Mapping[str, str] | None = None,
                max_log_bytes: int = 64 * 1024 * 1024) -> float:
    if not argv or any(not isinstance(a, str) or not a or "\0" in a for a in argv):
        raise ContractError("Process arguments must be nonempty strings without NUL.")
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ContractError("Process timeout must be a positive finite number.")
    if cancel:
        cancel()
    environment = os.environ.copy()
    environment.update(env_overrides or {})
    options: dict = {"start_new_session": True} if os.name != "nt" else {
        "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
    start = time.monotonic()
    with Path(log).open("xb") as stream:
        try:
            child = subprocess.Popen(argv, cwd=str(cwd), env=environment,
                                     stdin=subprocess.DEVNULL, stdout=stream,
                                     stderr=subprocess.STDOUT, shell=False, **options)
        except OSError as exc:
            raise ProcessError(f"Could not launch {Path(argv[0]).name}: {exc}") from exc
        try:
            while child.poll() is None:
                if cancel:
                    cancel()
                if time.monotonic() - start >= timeout:
                    raise RunTimeout(f"{Path(argv[0]).name} exceeded {timeout:g} seconds; see {log.name}.")
                if Path(log).stat().st_size > max_log_bytes:
                    raise ResourceError("Child log exceeded its size limit; process stopped.")
                time.sleep(0.05)
            if cancel:
                cancel()
            if Path(log).stat().st_size > max_log_bytes:
                raise ResourceError("Child log exceeded its size limit.")
            if child.returncode != 0:
                raise ProcessError(f"{Path(argv[0]).name} exited {child.returncode}; see {log.name}.")
        except BaseException:
            stop_process_tree(child)
            raise
    return time.monotonic() - start
