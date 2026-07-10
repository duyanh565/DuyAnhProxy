"""
mitmproxy addon — chạy nội bộ ở 127.0.0.1:8081
Tự động thay file game theo config.yaml
(Trang tải cert được phục vụ bởi cert_http.py, không phải addon này)
"""

import os
import yaml
from mitmproxy import http

CONFIG_PATH      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
REPLACEMENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "replacements")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class FileReplacer:
    def __init__(self):
        self.config  = load_config()
        self.rules   = self.config.get("rules", [])
        self.allowed = self.config.get("allowed_domains", [])

        print(f"[addon] Đã tải {len(self.rules)} rule(s).")
        for rule in self.rules:
            print(f"  - [{rule.get('app','')}] '{rule['match']}' → '{rule['replace_with']}'")

    def _allowed(self, host: str) -> bool:
        if not self.allowed:
            return True
        return any(host == d or host.endswith("." + d) for d in self.allowed)

    def response(self, flow: http.HTTPFlow) -> None:
        # BUG FIX: flow.response có thể là None nếu server không phản hồi
        if flow.response is None:
            return

        host     = flow.request.host
        url      = flow.request.pretty_url
        filename = url.split("?")[0].split("/")[-1]

        if not self._allowed(host):
            return

        for rule in self.rules:
            match = rule.get("match", "")
            if match and match in filename:
                path = os.path.join(REPLACEMENTS_DIR, rule["replace_with"])
                if os.path.exists(path):
                    try:
                        with open(path, "rb") as f:
                            content = f.read()
                        flow.response.content = content
                        flow.response.status_code = 200
                        for h in ["Content-Encoding", "Transfer-Encoding"]:
                            if h in flow.response.headers:
                                del flow.response.headers[h]
                        flow.response.headers["Content-Length"] = str(len(content))
                        flow.response.headers.setdefault("Content-Type", "application/octet-stream")
                        print(f"[✓] Thay: {filename} → {rule['replace_with']}")
                    except OSError as e:
                        print(f"[!] Lỗi đọc file thay: {path} — {e}")
                else:
                    print(f"[!] Không tìm thấy file thay: {path}")
                break


addons = [FileReplacer()]
