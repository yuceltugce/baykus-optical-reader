"""Local-network end-to-end demo: iPhone (Safari) -> this PC -> answers back.

    .venv/bin/python app/server.py            # then open the printed URL on the phone

Standard library only. Every request is saved under app/uploads/<time>/
(input, result.json, overlay.jpg) so each try can be looked at later.
"""
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import base64
import json
import socket
import ssl
import subprocess
import time
import traceback
import urllib.parse

import cv2

import pipeline

HERE = Path(__file__).resolve().parent
UPLOADS = HERE / "uploads"
PORT = 8000
MAX_BYTES = 200 * 1024 * 1024        # dataset PNGs are ~9000 px tall; iPhone PDFs are a few MB


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))     # no packet is sent; just picks the LAN interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (HERE / "static" / "index.html").read_bytes(), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/process":
            return self._send(404, b"not found", "text/plain")
        length = int(self.headers.get("Content-Length", 0))
        if not 0 < length <= MAX_BYTES:
            return self._send(413, json.dumps({"error": "Dosya boş ya da çok büyük."}).encode(), "application/json")
        name = urllib.parse.unquote(self.headers.get("X-Filename", "upload")) or "upload"
        try:
            data = self.rfile.read(length)
        except OSError as err:            # phone dropped the connection mid-upload; nobody left to answer
            print(f"[fail] {name}: connection lost during upload ({err})", flush=True)
            return
        if len(data) != length:
            print(f"[fail] {name}: incomplete upload {len(data)}/{length} bytes", flush=True)
            return self._send(400, json.dumps({"error": "Dosya tam gelmedi (bağlantı kesildi). Tekrar gönderin."},
                                              ensure_ascii=False).encode(), "application/json")
        run = UPLOADS / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        run.mkdir(parents=True)
        (run / ("input" + (Path(name).suffix.lower() or ".bin"))).write_bytes(data)
        started = time.time()
        try:
            result, overlay, working = pipeline.process(data, name)
            result["seconds"] = round(time.time() - started, 2)
            cv2.imwrite(str(run / "overlay.jpg"), overlay, [cv2.IMWRITE_JPEG_QUALITY, 85])
            cv2.imwrite(str(run / "working.jpg"), working, [cv2.IMWRITE_JPEG_QUALITY, 85])
            (run / "result.json").write_text(json.dumps(dict(result, filename=name), ensure_ascii=False, indent=2))
            ok, jpg = cv2.imencode(".jpg", overlay, [cv2.IMWRITE_JPEG_QUALITY, 80])
            result["overlay"] = "data:image/jpeg;base64," + base64.b64encode(jpg.tobytes()).decode()
            result["saved_to"] = str(run.relative_to(HERE.parent))
            print(f"[ok] {name} -> {run.name} ({result['seconds']} s) {result['summary']}", flush=True)
            self._send(200, json.dumps(result, ensure_ascii=False).encode(), "application/json")
        except (ValueError, cv2.error, RuntimeError) as err:
            (run / "error.txt").write_text(traceback.format_exc())
            print(f"[fail] {name}: {err}", flush=True)
            self._send(422, json.dumps({"error": str(err)}, ensure_ascii=False).encode(), "application/json")
        except Exception as err:   # never leave the phone waiting without an answer
            (run / "error.txt").write_text(traceback.format_exc())
            print(f"[fail] {name}: unexpected {type(err).__name__}: {err}", flush=True)
            self._send(500, json.dumps({"error": f"Beklenmeyen hata ({type(err).__name__}). Kayıt: {run.name}"},
                                       ensure_ascii=False).encode(), "application/json")

    def log_message(self, fmt, *args):
        pass


def self_signed_cert(ip):
    """iPhone Safari upgrades http:// to https://, so serve TLS with a local self-signed certificate.

    One certificate per LAN IP, kept in app/certs/ (git-ignored). Safari warns once
    ("This connection is not private"); that is expected for a certificate we made ourselves.
    """
    certs = HERE / "certs"
    certs.mkdir(exist_ok=True)
    cert, key = certs / f"{ip}.pem", certs / f"{ip}.key"
    if not cert.exists():
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "365",
                        "-keyout", str(key), "-out", str(cert), "-subj", "/CN=baykus-optik-local",
                        "-addext", f"subjectAltName=IP:{ip},IP:127.0.0.1,DNS:localhost"],
                       check=True, capture_output=True)
    return cert, key


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--http", action="store_true", help="plain HTTP (no certificate), e.g. for a desktop browser")
    parser.add_argument("--reference", help="reference scan if dataset/flat_front/004.png is not on disk")
    args = parser.parse_args()
    if args.reference:
        import run_experiment
        run_experiment.REFERENCE = str(Path(args.reference).resolve())
    pipeline.reference()                       # load reference + template once, before the first photo
    ip = local_ip()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    scheme = "http"
    if not args.http:
        cert, key = self_signed_cert(ip)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert, key)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    print(f"Hazır. iPhone'da (aynı Wi-Fi) Safari ile açın:  {scheme}://{ip}:{PORT}", flush=True)
    if scheme == "https":
        print("İlk açılışta 'Bu bağlantı gizli değil' uyarısı çıkar: Ayrıntıları Göster -> "
              "bu web sitesini ziyaret et -> Web Sitesini Ziyaret Et.", flush=True)
    print(f"Bu bilgisayarda: {scheme}://127.0.0.1:{PORT}    Durdurmak için Ctrl+C", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
