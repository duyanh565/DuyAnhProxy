"""
HTTP server nhỏ — chạy trên $PORT (Railway HTTP domain).
Phục vụ:
  /                       → Trang hướng dẫn: hiện IP, port + nút tải cert
  /mitmproxy.mobileconfig → Chỉ cài CA cert (fix lỗi SSL "truy xuất cấu hình")
  /cert.cer               → Cert dự phòng
  /cert.pem               → Cert dự phòng
  /health                 → Railway health-check
"""

import os
import plistlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
CERTS_DIR = os.path.join(BASE_DIR, "certs")
CERT_PEM  = os.path.join(CERTS_DIR, "mitmproxy-ca-cert.pem")
CERT_CER  = os.path.join(CERTS_DIR, "mitmproxy-ca-cert.cer")

_PROFILE_UUID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
_CERT_UUID    = "c3d4e5f6-a7b8-9012-cdef-012345678901"


def _make_mobileconfig_cert_only() -> bytes:
    """Dùng plistlib để tạo mobileconfig chuẩn — tránh lỗi 'Hồ sơ không hợp lệ'."""
    with open(CERT_CER, "rb") as f:
        cert_der = f.read()

    profile = {
        "PayloadDisplayName": "mitmproxy CA",
        "PayloadDescription": "mitmproxy CA Certificate",
        "PayloadIdentifier": "com.mitmproxy.cert.only",
        "PayloadOrganization": "mitmproxy",
        "PayloadRemovalDisallowed": False,
        "PayloadType": "Configuration",
        "PayloadUUID": _PROFILE_UUID,
        "PayloadVersion": 1,
        "PayloadContent": [
            {
                "PayloadType": "com.apple.security.root",
                "PayloadVersion": 1,
                "PayloadIdentifier": "com.mitmproxy.cert",
                "PayloadUUID": _CERT_UUID,
                "PayloadDisplayName": "mitmproxy CA",
                "PayloadContent": cert_der,  # plistlib tự encode base64
            }
        ],
    }
    return plistlib.dumps(profile, fmt=plistlib.FMT_XML)


def make_handler(proxy_host: str, proxy_port: int, cert_host: str = ""):

    class CertHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            print(f"[cert-http] {fmt % args}")

        def _send(self, code: int, ctype: str, body: bytes,
                  extra: Optional[dict] = None):
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
                self._send(200, "text/html; charset=utf-8",
                           _make_html(proxy_host, proxy_port, cert_host))

            elif path == "/mitmproxy.mobileconfig":
                if not os.path.exists(CERT_CER):
                    self._send(404, "text/plain", b"Cert not found")
                    return
                try:
                    data = _make_mobileconfig_cert_only()
                    self._send(
                        200, "application/x-apple-aspen-config", data,
                        {"Content-Disposition":
                         "attachment; filename=mitmproxy.mobileconfig"})
                except Exception as e:
                    print(f"[cert-http] Lỗi tạo mobileconfig: {e}")
                    self._send(500, "text/plain", b"Failed")

            elif path == "/cert.cer":
                if os.path.exists(CERT_CER):
                    with open(CERT_CER, "rb") as f:
                        data = f.read()
                    self._send(200, "application/pkix-cert", data,
                               {"Content-Disposition":
                                "attachment; filename=mitmproxy-ca.cer"})
                else:
                    self._send(404, "text/plain", b"Cert not found")

            elif path == "/cert.pem":
                if os.path.exists(CERT_PEM):
                    with open(CERT_PEM, "rb") as f:
                        data = f.read()
                    self._send(200, "application/x-pem-file", data,
                               {"Content-Disposition":
                                "attachment; filename=mitmproxy-ca.pem"})
                else:
                    self._send(404, "text/plain", b"Cert not found")

            else:
                self._send(404, "text/plain", b"Not found")

    return CertHandler


def _make_html(proxy_host: str, proxy_port: int, cert_host: str = "") -> bytes:
    html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>mitmproxy Setup</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
  background: #f2f2f7;
  padding: 20px;
  max-width: 480px;
  margin: auto;
}}
h1 {{ font-size: 22px; color: #1c1c1e; margin-bottom: 4px; }}
.sub {{ font-size: 13px; color: #8e8e93; margin-bottom: 20px; }}

.card {{
  background: #fff;
  border-radius: 16px;
  padding: 18px;
  margin: 12px 0;
  box-shadow: 0 1px 4px rgba(0,0,0,.08);
}}
h2 {{ font-size: 15px; color: #1c1c1e; margin-bottom: 12px; }}

/* Info box IP/Port */
.info-box {{
  background: #f2f2f7;
  border-radius: 12px;
  padding: 14px 16px;
  margin-bottom: 14px;
}}
.info-row {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
}}
.info-row:not(:last-child) {{
  border-bottom: 1px solid #e5e5ea;
}}
.info-label {{ font-size: 14px; color: #636366; }}
.info-value {{
  font-size: 20px;
  font-weight: 700;
  color: #007aff;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.5px;
}}

/* Steps */
.step {{
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin: 10px 0;
}}
.num {{
  background: #007aff;
  color: #fff;
  border-radius: 50%;
  min-width: 26px;
  height: 26px;
  font-size: 13px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}}
p {{ font-size: 14px; color: #3a3a3c; line-height: 1.8; }}
b {{ color: #1c1c1e; }}
code {{
  background: #e5e5ea;
  padding: 1px 6px;
  border-radius: 5px;
  font-size: 13px;
  font-weight: 600;
}}

/* Button */
a.btn {{
  display: block;
  padding: 16px;
  margin: 8px 0;
  border-radius: 13px;
  text-decoration: none;
  color: #fff;
  font-size: 17px;
  font-weight: 600;
  text-align: center;
}}
.blue {{ background: #007aff; }}
.gray {{ background: #8e8e93; }}

.sep {{ border: none; border-top: 1px solid #e5e5ea; margin: 14px 0; }}

.warn {{
  background: #fff3cd;
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 13px;
  color: #664d03;
  line-height: 1.7;
  margin-top: 10px;
}}
.err-fix {{
  background: #fce8e8;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 13px;
  color: #7b1d1d;
  line-height: 1.7;
  margin-bottom: 12px;
}}
</style>
</head>
<body>

<h1>✅ mitmproxy đang chạy</h1>
<p class="sub">HTTP Proxy — Free Fire / Free Fire Max</p>

<!-- ══ Link trang này ══ -->
{f'''<div class="card" style="background:#e8f4ff;border:1px solid #b3d4f5">
  <h2 style="color:#0055cc">🔗 Link trang cài đặt</h2>
  <p style="font-size:15px;font-weight:600;color:#007aff;word-break:break-all">
    https://{cert_host}/
  </p>
  <p style="font-size:12px;color:#636366;margin-top:6px">
    Chia sẻ link này để cài proxy trên iPhone khác
  </p>
</div>''' if cert_host else ''}

<!-- ══ Thông tin kết nối ══ -->
<div class="card">
  <h2>📡 Thông tin Proxy</h2>
  <div class="info-box">
    <div class="info-row">
      <span class="info-label">Server (IP / Host)</span>
      <span class="info-value">{proxy_host}</span>
    </div>
    <div class="info-row">
      <span class="info-label">Port</span>
      <span class="info-value">{proxy_port}</span>
    </div>
  </div>
  <p style="font-size:13px;color:#636366">
    Nhập thông tin này vào <b>WiFi → Cấu hình Proxy → Thủ công</b>
  </p>
</div>

<!-- ══ Bước 1: Cài cert (fix lỗi SSL) ══ -->
<div class="card">
  <div class="err-fix">
    🛑 <b>Fix lỗi "Không thể truy xuất cấu hình phiên bản"</b><br>
    Game lỗi vì iOS chưa tin cert của proxy. Cài file dưới là hết lỗi.
  </div>

  <h2>Bước 1 — Cài Certificate</h2>
  <a href="/mitmproxy.mobileconfig" class="btn blue">
    📲 Tải mitmproxy.mobileconfig
  </a>

  <hr class="sep">

  <div class="step">
    <div class="num">1</div>
    <p>Safari hỏi "Cho phép tải xuống?" → bấm <b>Cho phép</b></p>
  </div>
  <div class="step">
    <div class="num">2</div>
    <p><b>Cài đặt → Thông báo đã tải hồ sơ → Cài đặt</b> (góc phải trên) → nhập mã PIN → <b>Cài đặt</b> lần nữa → Xong</p>
  </div>
  <div class="step">
    <div class="num">3</div>
    <p><b>Cài đặt → Cài đặt chung → Giới thiệu → Cài đặt tin cậy chứng chỉ</b><br>
    Bật toggle cạnh <b>mitmproxy CA Cert</b></p>
  </div>

  <div class="warn">
    ⚠️ Bước 3 bắt buộc — thiếu bước này game vẫn báo lỗi dù proxy đang bật.
  </div>
</div>

<!-- ══ Bước 2: Cài proxy ══ -->
<div class="card">
  <h2>Bước 2 — Cài proxy vào WiFi</h2>

  <div class="step">
    <div class="num">1</div>
    <p><b>Cài đặt → WiFi → tên mạng đang kết nối → ⓘ</b></p>
  </div>
  <div class="step">
    <div class="num">2</div>
    <p>Cuộn xuống → <b>Cấu hình Proxy → Thủ công</b></p>
  </div>
  <div class="step">
    <div class="num">3</div>
    <p>
      <b>Máy chủ:</b> <code>{proxy_host}</code><br>
      <b>Cổng:</b> <code>{proxy_port}</code>
    </p>
  </div>
  <div class="step">
    <div class="num">4</div>
    <p>Bấm <b>Lưu</b> → mở Free Fire ✅</p>
  </div>
</div>

<!-- ══ Cert dự phòng ══ -->
<div class="card">
  <h2 style="color:#8e8e93;font-weight:500">Cert thủ công (nếu mobileconfig không được)</h2>
  <a href="/cert.cer" class="btn gray">📥 Tải cert.cer — iOS</a>
</div>

</body></html>"""
    return html.encode("utf-8")


def start_cert_server(http_port: int, proxy_host: str, proxy_port: int,
                      cert_host: str = ""):
    handler = make_handler(proxy_host, proxy_port, cert_host)
    server  = HTTPServer(("0.0.0.0", http_port), handler)
    print(f"[cert-http] Lắng nghe port {http_port}")
    server.serve_forever()
