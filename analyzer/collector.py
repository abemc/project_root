"""Lightweight HTTP collector that accepts POSTed usage entries and appends them to a central log.

Endpoint:
  POST /collect  -> accepts JSON object or JSON array of objects. Each object is a usage entry.

The collector writes entries via `usage_logger.append_usage_entries` and supports size-based rotation.
"""
import json
import threading
import http.server
import socketserver
from typing import List
import urllib.parse
import os
import ssl
import sys

from .usage_logger import append_usage_entries


class _CollectorHandler(http.server.BaseHTTPRequestHandler):
    server_version = "ProjectAnalyzerCollector/0.1"

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/collect":
            self.send_response(404)
            self.end_headers()
            return

        # authentication (optional)
        cfg = self.server.collector_config
        secret = cfg.get("auth_secret")
        if secret:
            # allow X-Shared-Secret, X-Collector-Secret header or Authorization: Bearer <secret>
            hdr = self.headers.get("X-Shared-Secret") or self.headers.get("X-Collector-Secret")
            auth = self.headers.get("Authorization")
            ok = False
            if hdr and hdr == secret:
                ok = True
            if auth and auth.strip().lower() == f"bearer {secret}".lower():
                ok = True
            if not ok:
                self.send_response(401)
                # CORS safe response
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"unauthorized")
                if hasattr(self.server, "log_func") and callable(self.server.log_func):
                    self.server.log_func(f"unauthorized request from {self.client_address}")
                return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else []
            if isinstance(payload, dict):
                entries = [payload]
            elif isinstance(payload, list):
                entries = payload
            else:
                raise ValueError("payload must be JSON object or array")
        except Exception as e:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))
            return

        # append entries to configured log
        cfg = self.server.collector_config
        try:
            append_usage_entries(cfg["path"], entries, max_bytes=cfg.get("max_bytes", 5 * 1024 * 1024), backup_count=cfg.get("backup_count", 5))
            self.send_response(200)
            # CORS headers for browser-based clients
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "X-Shared-Secret, X-Collector-Secret, Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            resp = {"received": len(entries)}
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            if hasattr(self.server, "log_func") and callable(self.server.log_func):
                self.server.log_func(f"received {len(entries)} entries from {self.client_address}")
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode("utf-8"))

    def do_OPTIONS(self):
        # respond to CORS preflight
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "X-Shared-Secret, X-Collector-Secret, Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
        self.end_headers()

    def do_GET(self):
        # simple health/healthcheck endpoint at / or /health
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))
            if hasattr(self.server, "log_func") and callable(self.server.log_func):
                self.server.log_func(f"health check from {self.client_address}")
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        # minimize logging; use server.log function if provided
        if hasattr(self.server, "log_func") and callable(self.server.log_func):
            self.server.log_func(format % args)


class CollectorServer:
    def __init__(self, path: str, host: str = "127.0.0.1", port: int = 0, max_bytes: int = 5 * 1024 * 1024, backup_count: int = 5, auth_secret: str | None = None, certfile: str | None = None, keyfile: str | None = None):
        self.path = path
        self.host = host
        self.port = port
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.auth_secret = auth_secret
        self.certfile = certfile
        self.keyfile = keyfile

        handler = _CollectorHandler
        self._httpd = socketserver.TCPServer((host, port), handler)
        # attach config to server
        self._httpd.collector_config = {"path": path, "max_bytes": max_bytes, "backup_count": backup_count, "auth_secret": auth_secret}
        self._httpd.log_func = lambda m: None
        self._thread = None

    def start(self):
        # background thread
        def _serve():
            try:
                self._httpd.serve_forever()
            except Exception:
                pass

        # if TLS cert provided, wrap server socket
        if self.certfile and self.keyfile:
            # Only enable TLS when both files exist; otherwise skip with a warning.
            try:
                if not (os.path.isfile(self.certfile) and os.path.isfile(self.keyfile)):
                    raise FileNotFoundError(f"certfile or keyfile not found: {self.certfile}, {self.keyfile}")
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(certfile=self.certfile, keyfile=self.keyfile)
                # wrap the socket
                self._httpd.socket = context.wrap_socket(self._httpd.socket, server_side=True)
            except FileNotFoundError as e:
                # log to stderr via server.log_func if available, otherwise print
                msg = f"TLS disabled: {e}"
                if hasattr(self._httpd, "log_func") and callable(self._httpd.log_func):
                    self._httpd.log_func(msg)
                else:
                    print(msg, file=sys.stderr)
            except Exception as e:
                # Any other SSL error should be surfaced and stop startup
                raise

        self._thread = threading.Thread(target=_serve, daemon=True)
        self._thread.start()
        # return the actual port (0 -> ephemeral)
        return self._httpd.server_address[1]

    def stop(self):
        try:
            self._httpd.shutdown()
            self._httpd.server_close()
        except Exception:
            pass
        if self._thread:
            self._thread.join(timeout=1.0)
