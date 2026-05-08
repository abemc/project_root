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
    def summarize(self, text: str, context: Optional[str] = None) -> str:
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
