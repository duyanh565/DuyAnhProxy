"""
mitmproxy addon — tự động thay file game theo rules trong config.yaml.
"""

import os
import yaml
from mitmproxy import http

CONFIG_PATH      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
REPLACEMENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "replacements")


class FileReplacer:
    def __init__(self):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        self.rules   = config.get("rules", [])
        self.allowed = config.get("allowed_domains", [])
        print(f"[addon] Đã tải {len(self.rules)} rule(s).")
        for r in self.rules:
            print(f"  [{r.get('app', '')}] '{r.get('match', '?')}' → '{r.get('replace_with', '?')}'")

    def _allowed_domain(self, host: str) -> bool:
        if not self.allowed:
            return True
        return any(host == d or host.endswith("." + d) for d in self.allowed)

    def response(self, flow: http.HTTPFlow) -> None:
        if flow.response is None:
            return
        host     = flow.request.host
        filename = flow.request.pretty_url.split("?")[0].split("/")[-1]

        if not self._allowed_domain(host):
            return

        for rule in self.rules:
            match = rule.get("match", "")
            if not match:
                continue
            if match in filename:
                replace_with = rule.get("replace_with", "")
                if not replace_with:
                    print(f"[!] Rule thiếu 'replace_with': {rule}")
                    continue
                path = os.path.join(REPLACEMENTS_DIR, replace_with)
                if os.path.exists(path):
                    try:
                        with open(path, "rb") as f:
                            content = f.read()
                        flow.response.content = content
                        flow.response.status_code = 200
                        for h in ["Content-Encoding", "Transfer-Encoding"]:
                            flow.response.headers.pop(h, None)
                        flow.response.headers["Content-Length"] = str(len(content))
                        flow.response.headers.setdefault(
                            "Content-Type", "application/octet-stream")
                        print(f"[✓] Thay: {filename} → {replace_with}")
                    except OSError as e:
                        print(f"[!] Lỗi đọc file thay: {path} — {e}")
                else:
                    print(f"[!] File thay không tồn tại: {path}")
                break


addons = [FileReplacer()]
