"""Cooperative single-host acquisition exclusion; not a distributed lease.

The OS releases the advisory lock when the handle/process closes. The lock file
is never deleted or treated as stale from its age or mere existence.
"""
from contextlib import contextmanager
from pathlib import Path
import os


@contextmanager
def local_source_lease(database_path: str | Path):
    path = Path(database_path).resolve()
    if not path.is_file():
        raise ValueError("SOURCE_WORKER_EXISTING_DATABASE_REQUIRED")
    lock_path = path.with_name(path.name + ".source-worker.lock")
    handle = open(lock_path, "a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                locked = True
            except OSError:
                raise RuntimeError("SOURCE_WORKER_ALREADY_ACTIVE") from None
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError:
                raise RuntimeError("SOURCE_WORKER_ALREADY_ACTIVE") from None
        yield
    finally:
        if locked:
            if os.name == "nt":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()
