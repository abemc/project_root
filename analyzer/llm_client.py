import abc
import logging
import os
import time
from typing import List, Optional

logger = logging.getLogger("analyzer.llm_client")


class LLMClient(abc.ABC):
    @abc.abstractmethod
    def summarize(self, text: str, context: Optional[str] = None) -> str:
        """Summarize a single text chunk."""

    @abc.abstractmethod
    def batch_summarize(self, chunks: List[str], strategy: str = "map_reduce") -> str:
        """Summarize multiple chunks using a strategy."""


class MockLLMClient(LLMClient):
    def __init__(self, default_context: Optional[str] = None):
        self.default_context = default_context

    def summarize(self, text: str, context: Optional[str] = None) -> str:
        # If caller provided no context, fall back to stored default_context
        ctx = context or self.default_context

        # Normalize text
        low = text.strip().lower()

        # If RFC3339/ISO requested anywhere, return RFC3339 timestamp
        if any(tok in low for tok in ["rfc3339", "iso 8601", "iso8601", "iso-8601"]):
            try:
                from datetime import datetime
                from zoneinfo import ZoneInfo

                now = datetime.now()
                if ctx and ("utc" in ctx.lower() or "jst" in ctx.lower() or "tokyo" in ctx.lower()):
                    try:
                        if "utc" in ctx.lower():
                            now = datetime.now(ZoneInfo("UTC"))
                        else:
                            now = datetime.now(ZoneInfo("Asia/Tokyo"))
                    except Exception:
                        pass
                # include timezone offset when possible
                try:
                    tz_dt = now.astimezone()
                except Exception:
                    tz_dt = now
                # format as RFC3339 without microseconds: YYYY-MM-DDThh:mm:ss+hh:mm
                try:
                    off = tz_dt.strftime('%z') or '+0000'
                    return tz_dt.strftime('%Y-%m-%dT%H:%M:%S') + off[:3] + ':' + off[3:]
                except Exception:
                    return tz_dt.replace(microsecond=0).isoformat()
            except Exception:
                pass

        # DATE queries (Japanese/English/Spanish/French)
        # Normalize by stripping surrounding punctuation to better match variations
        import re
        cleaned = re.sub(r"[\s\(\)\[\]（）．。\?\!！。、,，\"]+", " ", text).strip().lower()

        date_triggers = [
            "今日", "何月何日", "日付", "今日は何日", "今日は何月何日",
            "what is today's date", "what is today", "qué fecha es hoy", "qué día es hoy",
            "quelle est la date", "quelle date", "quelle jour",
        ]

        if any(tok in cleaned for tok in date_triggers):
            # If RFC3339/ISO requested, return RFC3339 timestamp
            if any(tok in low for tok in ["rfc3339", "iso 8601", "iso8601", "iso-8601"]):
                from datetime import datetime
                from zoneinfo import ZoneInfo

                now = datetime.now()
                # respect context timezone hint
                if ctx and ("utc" in ctx.lower() or "jst" in ctx.lower() or "tokyo" in ctx.lower()):
                    try:
                        if "utc" in ctx.lower():
                            now = datetime.now(ZoneInfo("UTC"))
                        else:
                            now = datetime.now(ZoneInfo("Asia/Tokyo"))
                    except Exception:
                        pass
                try:
                    tz_dt = now.astimezone()
                except Exception:
                    tz_dt = now
                try:
                    off = tz_dt.strftime('%z') or '+0000'
                    return tz_dt.strftime('%Y-%m-%dT%H:%M:%S') + off[:3] + ':' + off[3:]
                except Exception:
                    return tz_dt.replace(microsecond=0).isoformat()

            # If the analyzer UI provided an explicit date string in context, prefer that
            if ctx and re.search(r"\d{4}年|\d{4}-\d{2}-\d{2}|\d{4}/\d{2}/\d{2}", ctx):
                return ctx

            # Otherwise, return today's date formatted to the language of the query.
            from datetime import datetime
            try:
                from zoneinfo import ZoneInfo
                today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
            except Exception:
                today = datetime.now().date()
            # respond in detected language. Prefer Japanese when query contains Japanese
            # characters or when default context appears Japanese. Fallback order: Japanese -> French -> Spanish -> English
            def contains_japanese(s: str) -> bool:
                # basic heuristic: presence of Hiragana/Katakana/Kanji
                return bool(re.search(r"[\u3040-\u30FF\u4E00-\u9FFF]", s))

            # if query or context contains Japanese, prefer Japanese
            if contains_japanese(cleaned) or (ctx and contains_japanese(ctx)):
                # include weekday in Japanese response
                _weekdays = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
                weekday = _weekdays[today.weekday()]
                return f"今日の日付は {today.year}年{today.month}月{today.day}日（{weekday}）です。"

            # French
            if any(w in cleaned for w in ["quelle", "qu'est", "qu est", "quelle est"]):
                # French: e.g. "Nous sommes le 2026-05-09."
                return f"Nous sommes le {today.isoformat()}."
            # Spanish
            if any(w in cleaned for w in ["qué", "fecha", "dia", "día"]):
                return f"La fecha de hoy es {today.isoformat()}."
            # English
            if any(w in cleaned for w in ["what", "today"]):
                return f"Today's date is {today.isoformat()}."
            # default: English fallback
            return f"Today's date is {today.isoformat()}."

        # TIME queries (Japanese/English/Spanish/French)
        if any(k in low for k in ["何時", "何時ですか", "何時になっています", "what time", "current time", "hora", "quelle heure", "quelle est l'heure", "quelle heure est-il"]):
            # If context contains an explicit datetime or timezone, try to use it
            try:
                from datetime import datetime
                from zoneinfo import ZoneInfo

                # default: system local time
                now = datetime.now()

                # if user mentions '東京' or 'jst' or explicit Tokyo mention, use Asia/Tokyo
                if "東京" in low or "tokyo" in low or "jst" in low:
                    tz = ZoneInfo("Asia/Tokyo")
                    now = datetime.now(tz)
                # if context contains explicit timezone like 'UTC' or 'JST' use it
                elif ctx and ("utc" in ctx.lower() or "jst" in ctx.lower() or "tokyo" in ctx.lower()):
                    if "utc" in ctx.lower():
                        tz = ZoneInfo("UTC")
                        now = datetime.now(tz)
                    else:
                        tz = ZoneInfo("Asia/Tokyo")
                        now = datetime.now(tz)

                h = now.hour
                m = now.minute
                # language-specific response
                if any(w in low for w in ["what", "time"]):
                    return f"Current time is {h:02d}:{m:02d}."
                if any(w in low for w in ["qué", "hora"]):
                    return f"La hora actual es {h:02d}:{m:02d}."
                if any(w in low for w in ["quelle", "heure"]):
                    return f"Il est {h:02d}h{m:02d}."
                return f"現在の時刻は {h:02d}:{m:02d} です。"
            except Exception:
                from datetime import datetime

                now = datetime.now()
                return f"現在の時刻は {now.hour:02d}:{now.minute:02d} です。"

        # deterministic, cheap summary for testing
        head = text[:200]
        return f"[MOCK_SUMMARY length={len(text)}] " + (head if head else "(empty)")

    def batch_summarize(self, chunks: List[str], strategy: str = "map_reduce") -> str:
        parts = [self.summarize(c) for c in chunks]
        # naive reduce: concatenate
        return "\n".join(parts)


class OpenAIClient(LLMClient):
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, max_tokens: int = 1024, temperature: float = 0.2, max_retries: int = 2, backoff_factor: float = 1.0):
        # lazy import; raise informative error if package missing
        try:
            import openai  # type: ignore
        except Exception:
            raise RuntimeError("openai package not available; install with `pip install openai`")

        self.openai = openai
        # prefer explicit api_key, else respect environment or openai package config
        if api_key:
            self.openai.api_key = api_key

        self.model = model or (os.environ.get("OPENAI_MODEL") or "gpt-3.5-turbo")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        # usage logging
        self.usage_history: List[dict] = []
        # flushed entries are removed after write

    def _ensure_api_key(self):
        key = getattr(self.openai, "api_key", None) or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OpenAI API key not set. Provide api_key or set OPENAI_API_KEY environment variable.")

    def summarize(self, text: str, context: Optional[str] = None) -> str:
        """Summarize a single text chunk using OpenAI ChatCompletion."""
        self._ensure_api_key()
        messages = [
            {"role": "system", "content": "You are a concise assistant that summarizes text and extracts key points."},
            {"role": "user", "content": (f"Context: {context}\n\n" if context else "") + "Please summarize the following content concisely and list key points and potential TODOs:\n\n" + text},
        ]
        # perform request with simple retry for transient errors
        attempt = 0
        last_exc = None
        while attempt <= self.max_retries:
            try:
                resp = self.openai.ChatCompletion.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )

                # extract content
                content = resp["choices"][0]["message"]["content"].strip()

                # record usage if available
                usage = resp.get("usage") or {}
                entry = {
                    "timestamp": time.time(),
                    "model": self.model,
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                }
                self.usage_history.append(entry)
                logger.info("OpenAI summarize tokens: %s", entry)

                return content
            except Exception as e:
                last_exc = e
                # classify retryable errors if openai.errors available
                retryable = False
                try:
                    errs = getattr(self.openai, "error", None)
                    RateLimit = getattr(errs, "RateLimitError", None)
                    APIErr = getattr(errs, "APIError", None)
                    Timeout = getattr(errs, "Timeout", None)
                    if RateLimit and isinstance(e, RateLimit):
                        retryable = True
                    if APIErr and isinstance(e, APIErr):
                        retryable = True
                    if Timeout and isinstance(e, Timeout):
                        retryable = True
                except Exception:
                    retryable = False

                attempt += 1
                if not retryable or attempt > self.max_retries:
                    logger.exception("OpenAI API request failed (no more retries): %s", e)
                    raise RuntimeError(f"OpenAI API request failed: {e}")
                sleep_for = self.backoff_factor * (2 ** (attempt - 1))
                logger.warning("OpenAI transient error: %s — retrying in %.1fs (attempt %d)", e, sleep_for, attempt)
                time.sleep(sleep_for)

    def batch_summarize(self, chunks: List[str], strategy: str = "map_reduce") -> str:
        """Summarize multiple chunks. Default strategy is map-reduce."""
        if not chunks:
            return ""

        if strategy == "map_reduce":
            # map phase
            summaries = []
            for c in chunks:
                summaries.append(self.summarize(c))

            # reduce phase: summarize concatenated summaries
            combined = "\n\n".join(summaries)
            return self.summarize(combined)

        # fallback: summarize concatenation
        return self.summarize("\n\n".join(chunks))

    def flush_usage_to(self, path: str, max_bytes: int = 5 * 1024 * 1024, backup_count: int = 5) -> None:
        """Write accumulated usage_history to `path` as JSON-lines, then clear history.

        Performs rotation when file size exceeds `max_bytes`.
        """
        try:
            from .usage_logger import append_usage_entries
        except Exception:
            raise RuntimeError("usage_logger not available")

        if not self.usage_history:
            return

        entries = list(self.usage_history)
        append_usage_entries(path, entries, max_bytes=max_bytes, backup_count=backup_count)
        # clear flushed entries
        self.usage_history = []
