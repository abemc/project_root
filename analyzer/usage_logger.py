import json
import os
import tempfile
from typing import List

try:
    import fcntl
except Exception:
    fcntl = None


def _rotate_file(path: str, backup_count: int) -> None:
    # rotate path -> path.1, path.1 -> path.2, ... keep up to backup_count
    if backup_count <= 0:
        return
    for i in range(backup_count - 1, 0, -1):
        s = f"{path}.{i}"
        d = f"{path}.{i+1}"
        if os.path.exists(s):
            os.replace(s, d)
    if os.path.exists(path):
        os.replace(path, f"{path}.1")


def append_usage_entries(path: str, entries: List[dict], max_bytes: int = 5 * 1024 * 1024, backup_count: int = 5) -> None:
    """Append usage entries (list of dict) to JSON-lines file at `path`.

    This implementation writes entries to a temporary file, then acquires an inter-process lock
    (via a lockfile) and appends the temp contents to the main file atomically. After appending,
    if the file exceeds `max_bytes`, a simple rotation is performed. This reduces the risk of
    concurrent writers corrupting the log.
    """
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)

    # write entries to a temporary file in the same directory
    fd, tmp_path = tempfile.mkstemp(prefix=".usage_tmp_", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tf:
            for e in entries:
                tf.write(json.dumps(e, ensure_ascii=False) + "\n")
            tf.flush()
            os.fsync(tf.fileno())

        lock_path = path + ".lock"
        # open (or create) lock file
        with open(lock_path, "w") as lockf:
            if fcntl:
                try:
                    fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
                except Exception:
                    # fallback: continue without lock
                    pass

            # append temp file into main file
            mode = "a"
            with open(path, mode, encoding="utf-8") as mainf:
                with open(tmp_path, "r", encoding="utf-8") as tf:
                    for line in tf:
                        mainf.write(line)
                mainf.flush()
                try:
                    os.fsync(mainf.fileno())
                except Exception:
                    pass

            # check size and rotate if needed (still under lock)
            try:
                size = os.path.getsize(path)
                if size > max_bytes:
                    _rotate_file(path, backup_count)
            except OSError:
                pass

            if fcntl:
                try:
                    fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
