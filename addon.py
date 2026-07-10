"""
mitmproxy addon:
  1. Tự động thay file game theo config.yaml
  2. Khi truy cập http://cert.download/ → trả về cert để cài trên iPhone
"""

import os
import subprocess
import yaml
from mitmproxy import http

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
REPLACEMENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "replacements")
MITMPROXY_DIR = os.path.expanduser("~/.mitmproxy")
CERT_PEM = os.path.join(MITMPROXY_DIR, "mitmproxy-ca-cert.pem")

# Domain đặc biệt — truy cập qua proxy để tải cert
CERT_DOMAIN = "cert.download"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class FileReplacer:
    def __init__(self):
        self.config = load_config()
        self.rules = self.config.get("rules", [])
        self.allowed_domains = self.config.get("allowed_domains", [])
        print(f"[FileReplacer] Đã tải {len(self.rules)} rule(s).")
        for rule in self.rules:
            app = rule.get("app", "")
            print(f"  - [{app}] Khớp: '{rule['match']}' → '{rule['replace_with']}'")
        print(f"[FileReplacer] Truy cập http://{CERT_DOMAIN}/ qua proxy để tải cert")

    def _domain_allowed(self, host: str) -> bool:
        if not self.allowed_domains:
            return True
        return any(host == d or host.endswith("." + d) for d in self.allowed_domains)

    def request(self, flow: http.HTTPFlow) -> None:
        """Phục vụ cert khi truy cập http://cert.download/ qua proxy."""
        if flow.request.pretty_host == CERT_DOMAIN:
            path = flow.request.path

            if path in ("/", "/index.html"):
                # Trang chủ — hướng dẫn tải cert
                html = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tải Certificate</title>
<style>body{font-family:sans-serif;padding:30px;max-width:480px;margin:auto}
a.btn{display:block;padding:16px;margin:12px 0;border-radius:12px;
text-decoration:none;color:#fff;font-size:17px;font-weight:bold;text-align:center}
.green{background:#34c759}.blue{background:#007aff}
p{color:#555;font-size:13px;line-height:1.7}</style></head>
<body>
<h2>✅ mitmproxy đang chạy</h2>
<a href="/cert.cer" class="btn green">📥 Tải Certificate (.cer) — dành cho iOS</a>
<a href="/cert.pem" class="btn blue">Tải Certificate (.pem)</a>
<hr>
<p><b>Sau khi tải:</b><br>
1. Cài đặt → VPN và Quản lý thiết bị → bấm cert → Cài đặt<br>
2. Cài đặt → Cài đặt chung → Giới thiệu → Tin cậy chứng chỉ → bật mitmproxy</p>
</body></html>"""
                flow.response = http.Response.make(
                    200, html.encode(), {"Content-Type": "text/html; charset=utf-8"}
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
                    flow.response = http.Response.make(503, b"Cert chua san sang", {})

            elif path == "/cert.cer":
                if os.path.exists(CERT_PEM):
                    result = subprocess.run(
                        ["openssl", "x509", "-in", CERT_PEM, "-outform", "DER"],
                        capture_output=True
                    )
                    if result.returncode == 0:
                        flow.response = http.Response.make(200, result.stdout, {
                            "Content-Type": "application/pkix-cert",
                            "Content-Disposition": "attachment; filename=mitmproxy-ca.cer",
                        })
                    else:
                        flow.response = http.Response.make(500, b"Loi chuyen doi cert", {})
                else:
                    flow.response = http.Response.make(503, b"Cert chua san sang", {})

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
