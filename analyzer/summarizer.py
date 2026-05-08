from typing import List, Dict, Optional
from .llm_client import LLMClient
import os


def _read_full_or_snippet(root: str, meta: Dict, max_chars: int = 4000) -> str:
    path = os.path.join(root, meta["path"])
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
            return text[:max_chars]
    except Exception:
        # fall back to snippet provided by scanner
        return meta.get("snippet") or ""


def chunk_text(text: str, chunk_size: int = 2000) -> List[str]:
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def summarize_files(
    files_meta: List[Dict],
    root: str,
    llm: LLMClient,
    chunk_size: int = 2000,
    map_reduce: bool = True,
) -> str:
    """Summarize a set of files using the provided LLM client.

    Map-reduce: summarize chunks, then summarize the concatenation of summaries.
    """
    chunks = []
    for m in files_meta:
        text = _read_full_or_snippet(root, m, max_chars=chunk_size * 4)
        if not text:
            continue
        chunks.extend(chunk_text(text, chunk_size))

    if not chunks:
        return ""

    if not map_reduce:
        # naive: summarize concatenated
        return llm.summarize("\n\n".join(chunks))

    # map
    mapped = [llm.summarize(c) for c in chunks]
    # reduce
    reduced = llm.summarize("\n\n".join(mapped))
    return reduced
