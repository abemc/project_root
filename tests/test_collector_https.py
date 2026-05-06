import os
import shutil
import subprocess
import tempfile
import time
import unittest
import ssl
import json

from analyzer.collector import CollectorServer


class CollectorHTTPSTest(unittest.TestCase):
    def test_https_collect_with_selfsigned_cert(self):
        # require openssl for cert generation
        if shutil.which("openssl") is None:
            self.skipTest("openssl not available; skipping HTTPS test")

        with tempfile.TemporaryDirectory() as td:
            cert = os.path.join(td, "cert.pem")
            key = os.path.join(td, "key.pem")
            # generate self-signed cert (valid for 1 day)
            cmd = [
                "openssl",
                "req",
                "-x509",
                "-nodes",
                "-newkey",
                "rsa:2048",
                "-days",
                "1",
                "-subj",
                "/CN=127.0.0.1",
                "-keyout",
                key,
                "-out",
                cert,
            ]
            subprocess.check_call(cmd)

            path = os.path.join(td, "central.log")
            server = CollectorServer(path=path, host="127.0.0.1", port=0, max_bytes=200, backup_count=2, auth_secret="s3cr3t", certfile=cert, keyfile=key)
            port = server.start()
            try:
                # small delay to ensure server is listening
                time.sleep(0.2)
                import urllib.request

                data = json.dumps({"timestamp": 1.23, "total_tokens": 5}).encode("utf-8")
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(f"https://127.0.0.1:{port}/collect", data=data, headers={"Content-Type": "application/json", "X-Shared-Secret": "s3cr3t"}, method="POST")
                with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
                    body = resp.read().decode("utf-8")
                    j = json.loads(body)
                    self.assertEqual(j.get("received"), 1)

                self.assertTrue(os.path.exists(path))
            finally:
                server.stop()
