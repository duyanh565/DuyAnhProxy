"""
HTTP server nhỏ chạy song song với mitmproxy.
Mục đích:
  1. Railway health check → không bị crash
  2. Cho phép tải CA certificate qua trình duyệt (không cần mitm.it)
"""

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

MITMPROXY_HOME = os.path.expanduser("~/.mitmproxy")
CERT_PATH = os.path.join(MITMPROXY_HOME, "mitmproxy-ca-cert.pem")


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

        elif self.path in ("/cert.pem", "/cert.crt"):
            if os.path.exists(CERT_PATH):
                with open(CERT_PATH, "rb") as f:
                    data = f.read()
                ext = "pem" if self.path.endswith(".pem") else "crt"
                self.send_response(200)
                self.send_header("Content-Type", "application/x-pem-file")
                self.send_header("Content-Disposition", f"attachment; filename=mitmproxy-ca.{ext}")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self._send_html(503, "<h2>Certificate chưa sẵn sàng, thử lại sau 10 giây...</h2>")

        else:
            self._send_html(404, "<h2>404</h2>")

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
