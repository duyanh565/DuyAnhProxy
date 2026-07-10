"""
mitmproxy addon - Tự động thay file theo cấu hình trong config.yaml
"""

import os
import yaml
from mitmproxy import http

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
REPLACEMENTS_DIR = os.path.join(os.path.dirname(__file__), "replacements")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class FileReplacer:
    def __init__(self):
        self.config = load_config()
        self.rules = self.config.get("rules", [])
        self.allowed_domains = self.config.get("allowed_domains", [])
        print(f"[FileReplacer] Đã tải {len(self.rules)} rule(s).")
        if self.allowed_domains:
            print(f"[FileReplacer] Lọc domain: {self.allowed_domains}")
        else:
            print(f"[FileReplacer] Áp dụng cho TẤT CẢ domain.")
        for rule in self.rules:
            app = rule.get("app", "")
            print(f"  - [{app}] Khớp: '{rule['match']}' → '{rule['replace_with']}'")


    def _domain_allowed(self, host: str) -> bool:
        """Kiểm tra host có thuộc allowed_domains không."""
        if not self.allowed_domains:
            return True  # Không lọc → cho phép tất cả
        return any(host == d or host.endswith("." + d) for d in self.allowed_domains)

    def response(self, flow: http.HTTPFlow) -> None:
        host = flow.request.host
        url = flow.request.pretty_url
        filename = url.split("?")[0].split("/")[-1]  # Tên file cuối URL, bỏ query string

        # Bỏ qua nếu domain không nằm trong danh sách cho phép
        if not self._domain_allowed(host):
            return

        for rule in self.rules:
            match_name = rule.get("match", "")
            # Kiểm tra tên file trong URL có khớp với rule không
            if match_name and match_name in filename:
                replace_file = os.path.join(REPLACEMENTS_DIR, rule["replace_with"])
                if os.path.exists(replace_file):
                    with open(replace_file, "rb") as f:
                        content = f.read()

                    # Thay nội dung response
                    flow.response.content = content
                    flow.response.status_code = 200

                    # Xoá các header có thể gây lỗi
                    for h in ["Content-Encoding", "Transfer-Encoding"]:
                        if h in flow.response.headers:
                            del flow.response.headers[h]

                    flow.response.headers["Content-Length"] = str(len(content))

                    # Giữ nguyên Content-Type nếu có, hoặc dùng octet-stream
                    if "Content-Type" not in flow.response.headers:
                        flow.response.headers["Content-Type"] = "application/octet-stream"

                    print(f"[✓] Đã thay file: {filename} → {rule['replace_with']}  |  URL: {url}")
                else:
                    print(f"[!] Rule khớp nhưng file thay thế không tồn tại: {replace_file}")
                break  # Chỉ áp dụng rule đầu tiên khớp


addons = [FileReplacer()]
