"""
mitmproxy addon:
  1. Tự động thay file game theo config.yaml
  2. Khi truy cập http://<cert_host>:<port>/ trực tiếp → trả cert để cài trên iPhone
     (không cần cài proxy trước)
"""

import os
import yaml
from mitmproxy import http

# cryptography đã được cài sẵn cùng mitmproxy — không cần openssl CLI
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
REPLACEMENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "replacements")
MITMPROXY_DIR = os.path.expanduser("~/.mitmproxy")
CERT_PEM = os.path.join(MITMPROXY_DIR, "mitmproxy-ca-cert.pem")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def pem_to_der(pem_path: str) -> bytes:
    """Chuyển PEM → DER bằng thư viện cryptography (không cần openssl CLI)."""
    with open(pem_path, "rb") as f:
        cert = x509.load_pem_x509_certificate(f.read())
    return cert.public_bytes(Encoding.DER)


class FileReplacer:
    def __init__(self):
        self.config = load_config()
        self.rules = self.config.get("rules", [])
        self.allowed_domains = self.config.get("allowed_domains", [])
        self.cert_host = self.config.get("cert_host", "")
        self.proxy_port = int(self.config.get("port", 8080))

        print(f"[FileReplacer] Đã tải {len(self.rules)} rule(s).")
        for rule in self.rules:
            app = rule.get("app", "")
            print(f"  - [{app}] Khớp: '{rule['match']}' → '{rule['replace_with']}'")
        if self.cert_host:
            print(f"[FileReplacer] Tải cert tại: http://{self.cert_host}:{self.proxy_port}/")

    def _is_cert_request(self, host: str) -> bool:
        """Khớp nếu host là Railway proxy host."""
        if not self.cert_host:
            return False
        # pretty_host đã bỏ port rồi, so sánh trực tiếp với cert_host
        return host == self.cert_host

    def _domain_allowed(self, host: str) -> bool:
        if not self.allowed_domains:
            return True
        return any(host == d or host.endswith("." + d) for d in self.allowed_domains)

    def _serve_cert_page(self, flow: http.HTTPFlow) -> None:
        """Phục vụ trang tải cert."""
        path = flow.request.path.split("?")[0]  # bỏ query string nếu có

        if path in ("/", "/index.html"):
            cert_url = f"http://{self.cert_host}:{self.proxy_port}"
            html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tải Certificate</title>
<style>
body{{font-family:-apple-system,sans-serif;padding:24px;max-width:480px;margin:auto;background:#f2f2f7}}
h2{{color:#1c1c1e;font-size:20px}}
a.btn{{display:block;padding:16px;margin:12px 0;border-radius:14px;
text-decoration:none;color:#fff;font-size:17px;font-weight:600;text-align:center}}
.green{{background:#34c759}}.blue{{background:#007aff}}
.card{{background:#fff;border-radius:14px;padding:16px;margin:16px 0}}
p,li{{color:#3a3a3c;font-size:14px;line-height:1.8}}
code{{background:#e5e5ea;padding:2px 6px;border-radius:6px;font-size:13px}}
</style></head>
<body>
<h2>✅ Proxy đang chạy</h2>
<div class="card">
  <a href="{cert_url}/cert.cer" class="btn green">📥 Tải Certificate (.cer) — iOS</a>
  <a href="{cert_url}/cert.pem" class="btn blue">Tải Certificate (.pem)</a>
</div>
<div class="card">
  <p><b>Cách cài trên iPhone:</b></p>
  <ol>
    <li>Bấm <b>Tải Certificate (.cer)</b> → bấm <b>Cho phép</b></li>
    <li><b>Cài đặt</b> → <b>VPN và Quản lý thiết bị</b> → bấm <b>mitmproxy</b> → <b>Cài đặt</b></li>
    <li><b>Cài đặt</b> → <b>Cài đặt chung</b> → <b>Giới thiệu</b> → <b>Tin cậy chứng chỉ</b> → bật <b>mitmproxy</b></li>
  </ol>
  <p><b>Sau đó cài proxy WiFi:</b><br>
  Máy chủ: <code>{self.cert_host}</code><br>
  Cổng: <code>{self.proxy_port}</code></p>
</div>
</body></html>"""
            flow.response = http.Response.make(
                200, html.encode("utf-8"), {"Content-Type": "text/html; charset=utf-8"}
            )

        elif path == "/cert.pem":
            if os.path.exists(CERT_PEM):
                with open(CERT_PEM, "rb") as f:
                    data = f.read()
                flow.response = http.Response.make(200, data, {
                    "Content-Type": "application/x-pem-file",
                    "Content-Disposition": "attachment; filename=mitmproxy-ca.pem",
                })
            else:
                flow.response = http.Response.make(
                    503, b"Cert chua san sang, thu lai sau 10 giay", {}
                )

        elif path == "/cert.cer":
            if os.path.exists(CERT_PEM):
                try:
                    der_bytes = pem_to_der(CERT_PEM)
                    flow.response = http.Response.make(200, der_bytes, {
                        "Content-Type": "application/pkix-cert",
                        "Content-Disposition": "attachment; filename=mitmproxy-ca.cer",
                    })
                except Exception as e:
                    flow.response = http.Response.make(
                        500, f"Loi chuyen doi cert: {e}".encode(), {}
                    )
            else:
                flow.response = http.Response.make(
                    503, b"Cert chua san sang, thu lai sau 10 giay", {}
                )

        else:
            # Mọi path khác → 404 để tránh mitmproxy cố forward về chính nó
            flow.response = http.Response.make(404, b"Not found", {})

    def request(self, flow: http.HTTPFlow) -> None:
        host = flow.request.pretty_host  # không kèm port
        if self._is_cert_request(host):
            self._serve_cert_page(flow)

    def response(self, flow: http.HTTPFlow) -> None:
        """Thay thế file game khớp với rule trong config."""
        host = flow.request.host
        url = flow.request.pretty_url
        filename = url.split("?")[0].split("/")[-1]

        if not self._domain_allowed(host):
            return

        for rule in self.rules:
            match_name = rule.get("match", "")
            if match_name and match_name in filename:
                replace_file = os.path.join(REPLACEMENTS_DIR, rule["replace_with"])
                if os.path.exists(replace_file):
                    with open(replace_file, "rb") as f:
                        content = f.read()
                    flow.response.content = content
                    flow.response.status_code = 200
                    for h in ["Content-Encoding", "Transfer-Encoding"]:
                        if h in flow.response.headers:
                            del flow.response.headers[h]
                    flow.response.headers["Content-Length"] = str(len(content))
                    if "Content-Type" not in flow.response.headers:
                        flow.response.headers["Content-Type"] = "application/octet-stream"
                    print(f"[✓] Thay file: {filename} → {rule['replace_with']}")
                else:
                    print(f"[!] File thay thế không tồn tại: {replace_file}")
                break


addons = [FileReplacer()]
