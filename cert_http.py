"""
HTTP server nhỏ — chạy trên $PORT (Railway HTTP domain → HTTPS tự động).
Phục vụ trang tải cert. Không liên quan đến mitmproxy.
"""

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
CERTS_DIR = os.path.join(BASE_DIR, "certs")
CERT_PEM  = os.path.join(CERTS_DIR, "mitmproxy-ca-cert.pem")
CERT_CER  = os.path.join(CERTS_DIR, "mitmproxy-ca-cert.cer")


def make_handler(cert_host: str, proxy_port: int):

    class CertHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            print(f"[cert-http] {fmt % args}")

        def _send(self, code: int, ctype: str, body: bytes, extra: dict | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            if extra:
                for k, v in extra.items():
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]

            if path in ("/", "/index.html"):
                body = self._html()
                self._send(200, "text/html; charset=utf-8", body)

            elif path == "/cert.pem":
                if os.path.exists(CERT_PEM):
                    self._send(200, "application/x-pem-file",
                               open(CERT_PEM, "rb").read(),
                               {"Content-Disposition": "attachment; filename=mitmproxy-ca.pem"})
                else:
                    self._send(404, "text/plain", b"Cert not found")

            elif path == "/cert.cer":
                if os.path.exists(CERT_CER):
                    self._send(200, "application/pkix-cert",
                               open(CERT_CER, "rb").read(),
                               {"Content-Disposition": "attachment; filename=mitmproxy-ca.cer"})
                else:
                    self._send(404, "text/plain", b"Cert not found")

            else:
                self._send(404, "text/plain", b"Not found")

        def _html(self) -> bytes:
            html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tải Certificate</title>
<style>
body{{font-family:-apple-system,sans-serif;padding:24px;max-width:480px;margin:auto;background:#f2f2f7}}
h2{{color:#1c1c1e;font-size:20px;margin-bottom:4px}}
a.btn{{display:block;padding:16px;margin:12px 0;border-radius:14px;
text-decoration:none;color:#fff;font-size:17px;font-weight:600;text-align:center}}
.green{{background:#34c759}}.blue{{background:#007aff}}
.card{{background:#fff;border-radius:14px;padding:16px;margin:16px 0}}
p,li{{color:#3a3a3c;font-size:14px;line-height:1.9}}
code{{background:#e5e5ea;padding:2px 6px;border-radius:6px;font-size:13px}}
</style></head>
<body>
<h2>✅ Proxy đang chạy</h2>
<div class="card">
  <a href="/cert.cer" class="btn green">📥 Tải Certificate (.cer) — iOS</a>
  <a href="/cert.pem" class="btn blue">Tải Certificate (.pem)</a>
</div>
<div class="card">
  <p><b>Cách cài trên iPhone:</b></p>
  <ol>
    <li>Bấm <b>Tải Certificate (.cer)</b> → bấm <b>Cho phép</b></li>
    <li><b>Cài đặt</b> → <b>VPN và Quản lý thiết bị</b> → bấm <b>mitmproxy</b> → <b>Cài đặt</b></li>
    <li><b>Cài đặt</b> → <b>Cài đặt chung</b> → <b>Giới thiệu</b> → <b>Tin cậy chứng chỉ</b> → bật <b>mitmproxy</b></li>
  </ol>
  <p><b>Sau đó cài proxy WiFi:</b><br>
  Máy chủ: <code>{cert_host}</code><br>
  Cổng: <code>{proxy_port}</code></p>
</div>
</body></html>"""
            return html.encode("utf-8")

    return CertHandler


def start_cert_server(http_port: int, cert_host: str, proxy_port: int):
    handler = make_handler(cert_host, proxy_port)
    server  = HTTPServer(("0.0.0.0", http_port), handler)
    print(f"[cert-http] Lắng nghe port {http_port}")
    server.serve_forever()


def start_cert_server_thread(http_port: int, cert_host: str, proxy_port: int):
    t = threading.Thread(
        target=start_cert_server,
        args=(http_port, cert_host, proxy_port),
        daemon=True,
    )
    t.start()
    return t
