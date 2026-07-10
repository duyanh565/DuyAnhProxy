"""
HTTP server nhỏ chạy song song với mitmproxy.
Mục đích:
  1. Railway health check → không bị crash
  2. Cho phép tải CA certificate qua trình duyệt (không cần mitm.it)
"""

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
CERTS_DIR = os.path.join(BASE_DIR, "certs")
CERT_PEM  = os.path.join(CERTS_DIR, "mitmproxy-ca-cert.pem")
CERT_CER  = os.path.join(CERTS_DIR, "mitmproxy-ca-cert.cer")


class CertHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Tắt log mặc định

    def do_GET(self):
        if self.path in ("/", "/health"):
            self._send_html(200, """
            <html><body style="font-family:sans-serif;padding:40px">
            <h2>✅ mitmproxy đang chạy</h2>
            <p>Proxy server hoạt động bình thường.</p>
            <hr>
            <h3>📥 Tải Certificate cho iOS</h3>
            <p>Bấm nút bên dưới để tải certificate, sau đó cài và tin cậy trên iPhone:</p>
            <a href="/cert.pem" style="
              display:inline-block;padding:12px 24px;
              background:#007aff;color:white;
              border-radius:8px;text-decoration:none;font-size:16px">
              Tải Certificate (.pem)
            </a>
            <br><br>
            <a href="/cert.crt" style="
              display:inline-block;padding:12px 24px;
              background:#34c759;color:white;
              border-radius:8px;text-decoration:none;font-size:16px">
              Tải Certificate (.crt) — dùng nếu .pem không cài được
            </a>
            <hr>
            <p style="color:#888;font-size:13px">
              Sau khi tải: Cài đặt → VPN và Quản lý thiết bị → tin cậy chứng chỉ.<br>
              Rồi: Cài đặt → Cài đặt chung → Giới thiệu → Tin cậy chứng chỉ → bật mitmproxy.
            </p>
            </body></html>
            """)

        elif self.path == "/cert.pem":
            self._send_file(CERT_PEM, "mitmproxy-ca.pem", "application/x-pem-file")

        elif self.path == "/cert.cer":
            self._send_file(CERT_CER, "mitmproxy-ca.cer", "application/pkix-cert")

        else:
            self._send_html(404, "<h2>404</h2>")

    def _send_file(self, path, filename, mime):
        if os.path.exists(path):
            with open(path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Disposition", f"attachment; filename={filename}")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self._send_html(503, "<h2>File không tồn tại</h2>")

    def _send_html(self, code, html):
        data = html.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def start_cert_server(http_port: int):
    server = HTTPServer(("0.0.0.0", http_port), CertHandler)
    print(f"[CertServer] HTTP server chạy tại port {http_port}")
    print(f"[CertServer] Tải cert tại: http://0.0.0.0:{http_port}/cert.pem")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
