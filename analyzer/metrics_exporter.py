"""Simple Prometheus exporter for token usage collected by OpenAIClient.

Usage:
  pip install prometheus_client
  from analyzer.metrics_exporter import UsagePrometheusExporter
  exporter = UsagePrometheusExporter()
  exporter.start(port=8000)
  # periodically call exporter.update_from_client(client)
"""
import threading
import time
from typing import Optional


class UsagePrometheusExporter:
    def __init__(self):
        try:
            from prometheus_client import start_http_server, Counter, Gauge
        except Exception as e:
            raise RuntimeError("prometheus_client is required for metrics exporter (pip install prometheus_client)")

        self.start_http_server = start_http_server
        self.Counter = Counter
        self.Gauge = Gauge

        # define metrics
        self.prompt_tokens = self.Counter("analyzer_prompt_tokens_total", "Total prompt tokens used by analyzer")
        self.completion_tokens = self.Counter("analyzer_completion_tokens_total", "Total completion tokens used by analyzer")
        self.total_tokens = self.Counter("analyzer_total_tokens_total", "Total tokens used by analyzer")
        self.last_export_ts = self.Gauge("analyzer_last_export_timestamp", "Last export timestamp")

        # track last totals to avoid double-counting
        self._last_prompt = 0
        self._last_completion = 0
        self._last_total = 0
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self, port: int = 8000, interval: float = 30.0):
        """Start HTTP server and background update thread.

        The background thread expects an external client to be set via `set_client` or
        you can call `update_from_client(client)` manually.
        """
        self.start_http_server(port)
        self._running = True
        self._interval = interval
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def _run_loop(self):
        while self._running:
            try:
                # noop unless user calls update_from_client
                time.sleep(self._interval)
            except Exception:
                pass

    def update_from_client(self, client) -> None:
        """Update metrics using data from OpenAIClient. Expects client.usage_history or a counters dict."""
        # Sum totals from usage_history
        with self._lock:
            prompt_sum = 0
            completion_sum = 0
            total_sum = 0
            # if client has usage_history list
            hist = getattr(client, "usage_history", None)
            if hist is None:
                return
            for e in hist:
                p = e.get("prompt_tokens") or 0
                c = e.get("completion_tokens") or 0
                t = e.get("total_tokens") or 0
                prompt_sum += p
                completion_sum += c
                total_sum += t

            # compute deltas
            dp = max(0, prompt_sum - self._last_prompt)
            dc = max(0, completion_sum - self._last_completion)
            dt = max(0, total_sum - self._last_total)

            if dp:
                self.prompt_tokens.inc(dp)
            if dc:
                self.completion_tokens.inc(dc)
            if dt:
                self.total_tokens.inc(dt)

            self._last_prompt = prompt_sum
            self._last_completion = completion_sum
            self._last_total = total_sum
            self.last_export_ts.set(time.time())
