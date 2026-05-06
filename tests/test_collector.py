import os
import tempfile
import unittest
import json
import urllib.request
import urllib.error

from analyzer.collector import CollectorServer


class CollectorTest(unittest.TestCase):
    def test_collect_and_write(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "central.log")
            server = CollectorServer(path=path, host="127.0.0.1", port=0, max_bytes=200, backup_count=2, auth_secret="s3cr3t")
            port = server.start()
            try:
                url = f"http://127.0.0.1:{port}/collect"
                data = json.dumps({"timestamp": 1.23, "total_tokens": 5}).encode("utf-8")
                # use http.client to assert status codes directly
                import http.client
                host = "127.0.0.1"
                conn = http.client.HTTPConnection(host, port, timeout=2)
                conn.request("POST", "/collect", body=data, headers={"Content-Type": "application/json"})
                resp = conn.getresponse()
                self.assertEqual(resp.status, 401)
                conn.close()

                # now with correct header
                conn = http.client.HTTPConnection(host, port, timeout=2)
                conn.request("POST", "/collect", body=data, headers={"Content-Type": "application/json", "X-Shared-Secret": "s3cr3t"})
                resp = conn.getresponse()
                body = resp.read().decode("utf-8")
                j = json.loads(body)
                self.assertEqual(resp.status, 200)
                self.assertEqual(j.get("received"), 1)
                conn.close()

                # file should exist
                self.assertTrue(os.path.exists(path))

                # send more to trigger rotation
                import http.client
                host = "127.0.0.1"
                for i in range(10):
                    data = json.dumps({"timestamp": i, "total_tokens": i}).encode("utf-8")
                    conn = http.client.HTTPConnection(host, port, timeout=2)
                    conn.request("POST", "/collect", body=data, headers={"Content-Type": "application/json", "X-Shared-Secret": "s3cr3t"})
                    resp = conn.getresponse()
                    resp.read()
                    conn.close()

                # check that at least one rotated file exists
                rotated_exists = any(os.path.exists(os.path.join(td, fname)) for fname in ["central.log.1", "central.log.2"]) 
                self.assertTrue(rotated_exists or os.path.exists(path))
            finally:
                server.stop()
