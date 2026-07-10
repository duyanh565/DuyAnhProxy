"""
HTTP server nhỏ — chạy trên $PORT (Railway HTTP domain → HTTPS tự động).
Phục vụ trang hướng dẫn cài certificate mitmproxy và thông tin proxy.
Không liên quan đến mitmproxy.
"""

import base64
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
CERTS_DIR = os.path.join(BASE_DIR, "certs")
CERT_PEM  = os.path.join(CERTS_DIR, "mitmproxy-ca-cert.pem")
CERT_CER  = os.path.join(CERTS_DIR, "mitmproxy-ca-cert.cer")

# UUID cố định cho profile — không đổi mỗi lần request để iOS không bị trùng
_PROFILE_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
_CERT_UUID    = "c3d4e5f6-a7b8-9012-cdef-012345678901"


def _cert_b64() -> str:
    """Đọc file .cer (DER binary) và encode thành base64 để nhúng vào plist."""
    with open(CERT_CER, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _make_mobileconfig() -> bytes:
    """
    Tạo file .mobileconfig chỉ cài Certificate mitmproxy CA.
    Proxy vẫn do người dùng nhập IP + port tay vào WiFi settings.

    Tại sao phải cài cert?
    iOS chặn toàn bộ HTTPS nếu cert CA không được tin cậy.
    Không cài cert → proxy hoạt động nhưng HTTPS (game) bị lỗi SSL → không vô được.
    """
    cert_data = _cert_b64()

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>PayloadDisplayName</key>
  <string>mitmproxy CA Certificate</string>
  <key>PayloadDescription</key>
  <string>Cài certificate mitmproxy để proxy hoạt động được với HTTPS (game).</string>
  <key>PayloadIdentifier</key>
  <string>com.mitmproxy.cert.profile</string>
  <key>PayloadOrganization</key>
  <string>mitmproxy</string>
  <key>PayloadRemovalDisallowed</key>
  <false/>
  <key>PayloadType</key>
  <string>Configuration</string>
  <key>PayloadUUID</key>
  <string>{_PROFILE_UUID}</string>
  <key>PayloadVersion</key>
  <integer>1</integer>

  <key>PayloadContent</key>
  <array>
    <dict>
      <key>PayloadType</key>
      <string>com.apple.security.root</string>
      <key>PayloadVersion</key>
      <integer>1</integer>
      <key>PayloadIdentifier</key>
      <string>com.mitmproxy.cert</string>
      <key>PayloadUUID</key>
      <string>{_CERT_UUID}</string>
      <key>PayloadDisplayName</key>
      <string>mitmproxy CA Certificate</string>
      <key>PayloadContent</key>
      <data>{cert_data}</data>
    </dict>
  </array>
</dict>
</plist>"""
    return xml.encode("utf-8")


def make_handler(cert_host: str, proxy_host: str, external_port: int):

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

            if path == "/health":
                self._send(200, "text/plain", b"ok")

            elif path in ("/", "/index.html"):
                self._send(200, "text/html; charset=utf-8", self._html())

            elif path == "/cert.pem":
                if os.path.exists(CERT_PEM):
                    with open(CERT_PEM, "rb") as f:
                        data = f.read()
                    self._send(200, "application/x-pem-file", data,
                               {"Content-Disposition": "attachment; filename=mitmproxy-ca.pem"})
                else:
                    self._send(404, "text/plain", b"Cert not found")

            elif path == "/cert.cer":
                if os.path.exists(CERT_CER):
                    with open(CERT_CER, "rb") as f:
                        data = f.read()
                    self._send(200, "application/pkix-cert", data,
                               {"Content-Disposition": "attachment; filename=mitmproxy-ca.cer"})
                else:
                    self._send(404, "text/plain", b"Cert not found")

            elif path == "/mitmproxy.mobileconfig":
                # Cài certificate mitmproxy CA — bắt buộc để HTTPS (game) hoạt động qua proxy
                if os.path.exists(CERT_CER):
                    try:
                        data = _make_mobileconfig()
                        self._send(200, "application/x-apple-aspen-config", data,
                                   {"Content-Disposition": "attachment; filename=mitmproxy.mobileconfig"})
                    except Exception as e:
                        print(f"[cert-http] Lỗi tạo mobileconfig: {e}")
                        self._send(500, "text/plain", b"Failed to generate mobileconfig")
                else:
                    self._send(404, "text/plain", b"Cert not found")

            else:
                self._send(404, "text/plain", b"Not found")

        def _html(self) -> bytes:
            html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>mitmproxy — Cài đặt</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:-apple-system,sans-serif;padding:20px;max-width:500px;margin:auto;background:#f2f2f7}}
h2{{color:#1c1c1e;font-size:20px;margin:0 0 16px}}
h3{{color:#1c1c1e;font-size:15px;font-weight:700;margin:0 0 8px}}
a.btn{{display:block;padding:15px;margin:8px 0;border-radius:13px;
  text-decoration:none;color:#fff;font-size:16px;font-weight:600;text-align:center}}
.green{{background:#34c759}}.gray{{background:#636366}}
.card{{background:#fff;border-radius:14px;padding:16px;margin:12px 0;
  box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.step{{display:flex;gap:12px;align-items:flex-start;margin:8px 0}}
.num{{background:#007aff;color:#fff;border-radius:50%;width:24px;height:24px;
  font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center;
  flex-shrink:0;margin-top:1px}}
.warn{{background:#fff3cd;border-radius:10px;padding:10px 14px;margin-top:10px;
  font-size:13px;color:#664d03;line-height:1.7}}
.proxy-box{{background:#f2f2f7;border-radius:10px;padding:12px 14px;margin:10px 0}}
p,li{{color:#3a3a3c;font-size:14px;line-height:1.8;margin:0}}
code{{background:#e5e5ea;padding:2px 7px;border-radius:6px;font-size:14px;
  font-weight:600;letter-spacing:.3px}}
.sep{{border:none;border-top:1px solid #e5e5ea;margin:14px 0}}
</style></head>
<body>
<h2>✅ mitmproxy đang chạy</h2>

<!-- ══ BƯỚC 1: Cài cert ══ -->
<div class="card">
  <h3>Bước 1 — Cài Certificate mitmproxy <span style="color:#ff3b30">⚠️ Bắt buộc</span></h3>
  <a href="/mitmproxy.mobileconfig" class="btn green">
    📲 Tải mitmproxy.mobileconfig
  </a>
  <div class="warn">
    ⚠️ <b>Phải cài bước này trước.</b> Nếu không cài certificate, iOS sẽ chặn toàn bộ kết nối HTTPS → không vào game được dù đã nhập đúng IP và port.
  </div>
  <hr class="sep">
  <p style="color:#636366;font-size:13px;margin-top:2px">Sau khi tải file:</p>
  <div class="step"><div class="num">1</div>
    <p>Bấm <b>Cho phép</b> khi Safari hỏi</p></div>
  <div class="step"><div class="num">2</div>
    <p><b>Cài đặt → VPN và Quản lý thiết bị → mitmproxy CA Certificate → Cài đặt</b></p></div>
  <div class="step"><div class="num">3</div>
    <p><b>Cài đặt → Cài đặt chung → Giới thiệu → Tin cậy chứng chỉ → bật mitmproxy</b><br>
    <span style="color:#636366;font-size:13px">(Bước này iOS bắt buộc — không thể bỏ qua)</span></p></div>
</div>

<!-- ══ BƯỚC 2: Nhập IP + Port ══ -->
<div class="card">
  <h3>Bước 2 — Nhập IP và Port vào WiFi</h3>
  <div class="proxy-box">
    <p>Máy chủ (IP):&nbsp; <code>{proxy_host}</code></p>
    <p style="margin-top:6px">Cổng (Port):&nbsp;&nbsp; <code>{external_port}</code></p>
  </div>
  <div class="step"><div class="num">1</div>
    <p><b>Cài đặt → WiFi → [Tên mạng WiFi] → nhấn ⓘ</b></p></div>
  <div class="step"><div class="num">2</div>
    <p>Kéo xuống <b>Cấu hình Proxy → Thủ công</b></p></div>
  <div class="step"><div class="num">3</div>
    <p>Nhập <b>Máy chủ</b> và <b>Cổng</b> như trên → <b>Lưu</b></p></div>
</div>

<!-- ══ Tải cert riêng (dự phòng) ══ -->
<div class="card">
  <h3 style="color:#636366;font-weight:600">Dự phòng — Tải cert thủ công</h3>
  <a href="/cert.cer" class="btn gray">📥 Tải Certificate (.cer) — iOS</a>
  <a href="/cert.pem" class="btn gray">Tải Certificate (.pem) — Android / PC</a>
</div>

</body></html>"""
            return html.encode("utf-8")

    return CertHandler


def start_cert_server(http_port: int, cert_host: str, proxy_host: str, external_port: int):
    handler = make_handler(cert_host, proxy_host, external_port)
    server  = HTTPServer(("0.0.0.0", http_port), handler)
    print(f"[cert-http] Lắng nghe port {http_port}")
    server.serve_forever()
