import os
import fnmatch
import hashlib
from typing import List, Dict, Optional

DEFAULT_EXCLUDES = [".git", "node_modules", "__pycache__", ".venv", "venv", "build", "dist"]
DEFAULT_EXTENSIONS = [
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".js", ".ts", ".java"
]


def _lang_from_ext(path: str) -> str:
    _, ext = os.path.splitext(path)
    return ext.lstrip(".") or "binary"


def _sha256_of_file(path: str, max_bytes: Optional[int] = None) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        if max_bytes is None:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        else:
            h.update(f.read(max_bytes))
    return h.hexdigest()


def _is_excluded(path: str, exclude_patterns: List[str]) -> bool:
    for pat in exclude_patterns:
        if pat in path:
            return True
        if fnmatch.fnmatch(path, pat):
            return True
    return False


def scan(
    root: str = ".",
    include_extensions: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    max_snippet_lines: int = 20,
    size_threshold: int = 1_000_000,
) -> Dict:
    """Scan a workspace and return metadata about files.

    Returns a dict with keys: project_summary (minimal), files (list of metadata)
    """
    if include_extensions is None:
        include_extensions = DEFAULT_EXTENSIONS
    if exclude_patterns is None:
        exclude_patterns = DEFAULT_EXCLUDES

    files = []
    total_lines = 0
    lang_count = {}

    for dirpath, dirnames, filenames in os.walk(root):
        # prune excluded directories in-place
        dirnames[:] = [d for d in dirnames if not _is_excluded(os.path.join(dirpath, d), exclude_patterns)]

        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            rel = os.path.relpath(fpath, root)
            if _is_excluded(rel, exclude_patterns):
                continue

            _, ext = os.path.splitext(fname)
            if ext and ext.lower() not in include_extensions:
                continue

            try:
                st = os.stat(fpath)
            except OSError:
                continue

            size = st.st_size
            lang = _lang_from_ext(fname)
            lang_count[lang] = lang_count.get(lang, 0) + 1

            snippet = None
            sha256 = None
            is_large = size > size_threshold

            if not is_large:
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        lines = []
                        for i, line in enumerate(f):
                            if i >= max_snippet_lines:
                                break
                            lines.append(line.rstrip("\n"))
                        snippet = "\n".join(lines)
                        # compute hash of entire file
                    sha256 = _sha256_of_file(fpath)
                except Exception:
                    snippet = None
            else:
                # for large files, compute hash of first 64KB
                try:
                    sha256 = _sha256_of_file(fpath, max_bytes=65536)
                except Exception:
                    sha256 = None

            file_meta = {
                "path": rel,
                "size": size,
                "lang": lang,
                "snippet": snippet,
                "sha256": sha256,
                "is_large": is_large,
            }
            files.append(file_meta)

    summary = {
        "total_files": len(files),
        "top_languages": sorted(lang_count.items(), key=lambda x: -x[1])[:5],
    }

    return {"project_summary": summary, "files": files}


if __name__ == "__main__":
    import json
    print(json.dumps(scan("."), indent=2, ensure_ascii=False))
