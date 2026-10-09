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
import re
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

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json")

    def do_POST(self):
        if self.path == "/api/confirm":
            return self.confirm()
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
            result["run"] = run.name
            if result["retake"]:              # nothing to show: only say why and ask for a new scan
                print(f"[retake] {name} -> {run.name}: {result['rescan_reasons']}", flush=True)
                return self._json(200, dict(run=run.name, retake=result["retake"], seconds=result["seconds"]))
            result["overlay"] = data_url(overlay, 80)
            for c in result["confirm"]:       # the question's row from the plain photo, enlarged
                x0, y0, x1, y1 = c["box"]
                c["image"] = data_url(cv2.resize(working[y0:y1, x0:x1], None, fx=2, fy=2,
                                                 interpolation=cv2.INTER_CUBIC), 85)
            print(f"[ok] {name} -> {run.name} ({result['seconds']} s) {result['summary']}", flush=True)
            self._json(200, result)
        except pipeline.MarkersNotFound as err:
            (run / "error.txt").write_text(traceback.format_exc())
            print(f"[retake] {name}: {err}", flush=True)
            self._json(200, dict(run=run.name, retake=[pipeline.RETAKE_TEXT["markers"]]))
        except (ValueError, cv2.error, RuntimeError) as err:
            (run / "error.txt").write_text(traceback.format_exc())
            print(f"[fail] {name}: {err}", flush=True)
            self._send(422, json.dumps({"error": str(err)}, ensure_ascii=False).encode(), "application/json")
        except Exception as err:   # never leave the phone waiting without an answer
            (run / "error.txt").write_text(traceback.format_exc())
            print(f"[fail] {name}: unexpected {type(err).__name__}: {err}", flush=True)
            self._send(500, json.dumps({"error": f"Beklenmeyen hata ({type(err).__name__}). Kayıt: {run.name}"},
                                       ensure_ascii=False).encode(), "application/json")

    def confirm(self):
        """Save the student's choices for the questions the reader was unsure about (confirmed.json)."""
        try:
            body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", 0)), 1_000_000)))
            run = UPLOADS / str(body["run"])
            if not RUN_NAME.fullmatch(str(body["run"])) or not (run / "result.json").exists():
                return self._json(404, {"error": "Kayıt bulunamadı."})
            choices = {str(k): str(v) for k, v in dict(body["choices"]).items()}
            if not all(v in VALID_CHOICES for v in choices.values()):
                return self._json(400, {"error": "Geçersiz seçim."})
        except (ValueError, KeyError, TypeError):
            return self._json(400, {"error": "İstek okunamadı."})
        result = json.loads((run / "result.json").read_text())
        final = {s: {str(r["question"]): r["answer"] or "-" for r in rows} for s, rows in result["answers"].items()}
        for key, value in choices.items():            # "fen-12": "B"
            subject, _, q = key.partition("-")
            if subject in final and q in final[subject]:
                final[subject][q] = value
        (run / "confirmed.json").write_text(json.dumps(dict(choices=choices, answers=final, saved=datetime.now().isoformat(
            timespec="seconds")), ensure_ascii=False, indent=2))
        print(f"[confirm] {run.name}: {choices}", flush=True)
        self._json(200, {"ok": True})

    def log_message(self, fmt, *args):
        pass


RUN_NAME = re.compile(r"\d{8}-\d{6}-\d{6}")
VALID_CHOICES = {"A", "B", "C", "D", "E", "-"}


def data_url(image, quality):
    ok, jpg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return "data:image/jpeg;base64," + base64.b64encode(jpg.tobytes()).decode()


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
