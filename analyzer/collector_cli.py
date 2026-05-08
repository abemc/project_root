import argparse
import shutil
import subprocess
import os
import sys
import time

from .collector import CollectorServer


def generate_self_signed(cert_path: str, key_path: str, cn: str = "127.0.0.1") -> None:
    """Generate a self-signed cert using openssl CLI. Requires openssl to be available."""
    if shutil.which("openssl") is None:
        raise RuntimeError("openssl not available to generate certificates")

    cmd = [
        "openssl",
        "req",
        "-x509",
        "-nodes",
        "-newkey",
        "rsa:2048",
        "-days",
        "365",
        "-subj",
        f"/CN={cn}",
        "-keyout",
        key_path,
        "-out",
        cert_path,
    ]
    subprocess.check_call(cmd)


def main(argv=None):
    p = argparse.ArgumentParser(description="Start CollectorServer for usage logs (supports TLS)")
    p.add_argument("--path", required=True, help="Path to central log file")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8001)
    p.add_argument("--auth-secret", default=None, help="Shared secret for POST authentication")
    p.add_argument("--certfile", default=None, help="TLS cert file path (PEM)")
    p.add_argument("--keyfile", default=None, help="TLS key file path (PEM)")
    p.add_argument("--generate-cert", action="store_true", help="Generate a self-signed cert if cert/key not provided (requires openssl)")
    args = p.parse_args(argv)

    certfile = args.certfile
    keyfile = args.keyfile
    if args.generate_cert and (not certfile or not keyfile):
        # write into same directory as log
        d = os.path.dirname(os.path.abspath(args.path)) or "."
        certfile = certfile or os.path.join(d, "collector_cert.pem")
        keyfile = keyfile or os.path.join(d, "collector_key.pem")
        print(f"Generating self-signed cert -> {certfile}, {keyfile}")
        generate_self_signed(certfile, keyfile)

    server = CollectorServer(path=args.path, host=args.host, port=args.port, auth_secret=args.auth_secret, certfile=certfile, keyfile=keyfile)
    port = server.start()
    print(f"CollectorServer started on {args.host}:{port} (log: {args.path})")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down CollectorServer...")
        server.stop()


if __name__ == "__main__":
    main()
