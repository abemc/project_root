from typing import List, Dict, Optional
from .llm_client import LLMClient
import os
import time
import logging

# logger for detailed summarizer traces
logger = logging.getLogger(__name__)
if not logger.handlers:
    h = logging.FileHandler('/tmp/summarizer.log')
    h.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(h)
    logger.setLevel(logging.DEBUG)


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
    start_all = time.time()
    logger.debug('summarize_files start files_meta=%d chunk_size=%d map_reduce=%s', len(files_meta), chunk_size, map_reduce)
    chunks = []
    chunk_sources = []
    for fi, m in enumerate(files_meta):
        t0 = time.time()
        text = _read_full_or_snippet(root, m, max_chars=chunk_size * 4)
        dur = (time.time() - t0) * 1000.0
        if not text:
            logger.debug('file[%d] %s: no text (read took %.1fms)', fi, m.get('path'), dur)
            continue
        added = chunk_text(text, chunk_size)
        for j, ch in enumerate(added):
            chunks.append(ch)
            chunk_sources.append({"path": m.get('path'), "index_in_file": j})
        logger.debug('file[%d] %s: read %.1fms added_chunks=%d text_len=%d', fi, m.get('path'), dur, len(added), len(text))

    if not chunks:
        return ""

    if not map_reduce:
        # naive: summarize concatenated
        t0 = time.time()
        out = llm.summarize("\n\n".join(chunks))
        logger.debug('summarize naive completed in %.1fms output_len=%d', (time.time() - t0) * 1000.0, len(out) if isinstance(out, str) else 0)
        logger.debug('summarize_files total_time=%.1fms', (time.time() - start_all) * 1000.0)
        return out

    # map
    mapped = []
    map_start = time.time()
    for i, c in enumerate(chunks):
        t0 = time.time()
        try:
            r = llm.summarize(c)
        except Exception as e:
            r = ''
            logger.exception('llm.summarize exception on chunk %d: %s', i, e)
        dt = (time.time() - t0) * 1000.0
        mapped.append(r)
        src_info = chunk_sources[i] if i < len(chunk_sources) else {"path": "<unknown>", "index_in_file": -1}
        logger.debug('map chunk %d/%d done dt=%.1fms chunk_len=%d out_len=%d source=%s index_in_file=%d',
                     i + 1,
                     len(chunks),
                     dt,
                     len(c),
                     len(r) if isinstance(r, str) else 0,
                     src_info.get("path"),
                     src_info.get("index_in_file"))
    map_total = (time.time() - map_start) * 1000.0
    logger.debug('map phase completed chunks=%d total_ms=%.1f', len(chunks), map_total)
    # reduce
    red_t0 = time.time()
    reduced = ''
    try:
        reduced = llm.summarize("\n\n".join(mapped))
    except Exception as e:
        logger.exception('llm.summarize exception during reduce: %s', e)
    red_dt = (time.time() - red_t0) * 1000.0
    logger.debug('reduce completed ms=%.1f out_len=%d', red_dt, len(reduced) if isinstance(reduced, str) else 0)
    logger.debug('summarize_files total_time=%.1fms', (time.time() - start_all) * 1000.0)
    return reduced
