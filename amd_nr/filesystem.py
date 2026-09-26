"""Private workspaces, integrity checks, exclusive publication and JSON I/O."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Iterator

from .errors import ContractError, ResourceError


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path, limit: int = 1024 * 1024) -> dict:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ContractError(f"Expected a regular JSON file: {path.name}")
    if path.stat().st_size > limit:
        raise ContractError(f"JSON exceeds {limit} bytes: {path.name}")
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"),
                          object_pairs_hook=_unique_object,
                          parse_constant=lambda value: (_ for _ in ()).throw(ContractError(f"Non-finite JSON number: {value}")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"Invalid UTF-8 JSON: {path.name}") from exc
    if not isinstance(data, dict):
        raise ContractError(f"Expected a JSON object: {path.name}")
    return data


def write_json(path: Path, value: dict) -> None:
    """Atomic replacement inside a private job directory (not media publishing)."""
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix=".json-", dir=path.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def check_disk(root: Path, required: int, reserve: int) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(root).free < required + reserve:
        raise ResourceError(f"Insufficient disk space: need {required + reserve:,} bytes including reserve.")


@contextmanager
def workspace_lock(root: Path) -> Iterator[None]:
    """OS-held lock survives exceptions and is released automatically on crashes.

    Scope is this work root, not the whole GPU. Multiple roots/external processes
    can still contend. The lock file is deliberately never unlinked (inode race).
    """
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".native.lock"
    if path.is_symlink():
        raise ResourceError("Refusing a symbolic-link lock file.")
    with path.open("a+b") as f:
        f.seek(0, os.SEEK_END)
        if f.tell() == 0:
            f.write(b"\0")
            f.flush()
        f.seek(0)
        locked = False
        try:
            if os.name == "nt":
                import msvcrt
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise ResourceError("A native job already owns this work directory.") from exc
            else:
                import fcntl
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError as exc:
                    raise ResourceError("A native job already owns this work directory.") from exc
            locked = True
            yield
        finally:
            if locked:
                f.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def publish_new_file(source: Path, destination: Path) -> None:
    """Never overwrite user files. Copy completely, then link atomically.

    Hardlink publication is supported by NTFS and normal local Linux filesystems.
    Fail closed when the destination filesystem does not support it, rather than
    exposing a partially copied media file under the final name.
    """
    source, destination = Path(source), Path(destination)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Output exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".amd-nr-publish-", dir=destination.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as out, source.open("rb") as inp:
            shutil.copyfileobj(inp, out, 1024 * 1024)
            out.flush()
            os.fsync(out.fileno())
        os.link(temp, destination)  # Atomic no-replace, same destination volume.
    except FileExistsError:
        raise
    except OSError as exc:
        raise ResourceError("Atomic publication failed. Use a local NTFS/ext4-like destination with hardlink support.") from exc
    finally:
        temp.unlink(missing_ok=True)
