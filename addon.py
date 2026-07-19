"""
mitmproxy addon — tự động thay file game theo rules trong config.yaml.
"""

import os
import yaml
from mitmproxy import http

CONFIG_PATH      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
REPLACEMENTS_DIR = os.path.dirname(os.path.abspath(__file__))


class FileReplacer:
    def __init__(self):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        self.rules   = config.get("rules", [])
        self.allowed = config.get("allowed_domains", [])
        print(f"[addon] REPLACEMENTS_DIR = {REPLACEMENTS_DIR}")
        print(f"[addon] Đã tải {len(self.rules)} rule(s).")
        for r in self.rules:
            rpath = os.path.join(REPLACEMENTS_DIR, r.get("replace_with", ""))
            exists = os.path.exists(rpath)
            print(f"  [{r.get('app','')}] match='{r.get('match','?')}' "
                  f"→ file='{rpath}' exists={exists}")

    def _allowed_domain(self, host: str) -> bool:
        if not self.allowed:
            return True
        return any(host == d or host.endswith("." + d) for d in self.allowed)

    def request(self, flow: http.HTTPFlow) -> None:
        """Log mọi request để thấy proxy có bắt được traffic không."""
        host = flow.request.host
        url  = flow.request.pretty_url
        if any(kw in host for kw in ["garena", "freefire", "gmc"]):
            print(f"[req] {flow.request.method} {url[:120]}")

    def response(self, flow: http.HTTPFlow) -> None:
        if flow.response is None:
            return
        host     = flow.request.host
        full_url = flow.request.pretty_url.split("?")[0]
        filename = full_url.split("/")[-1]

        # Log mọi response từ domain game
        if any(kw in host for kw in ["garena", "freefire", "gmc"]):
            print(f"[res] {host} | file='{filename}' | status={flow.response.status_code}")

        if not self._allowed_domain(host):
            if any(kw in host for kw in ["garena", "freefire", "gmc"]):
                print(f"[skip] domain không trong allowed_domains: {host}")
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
                print(f"[match] Khớp rule '{match}' | tìm file: {path}")
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
                        print(f"[✓] Đã thay: {filename} → {replace_with} ({len(content)} bytes)")
                    except OSError as e:
                        print(f"[!] Lỗi đọc file thay: {path} — {e}")
                else:
                    print(f"[!] File thay KHÔNG TỒN TẠI: {path}")
                    print(f"[!] Các file hiện có trong {REPLACEMENTS_DIR}:")
                    try:
                        files = os.listdir(REPLACEMENTS_DIR)
                        for fn in files:
                            print(f"    - {fn}")
                    except Exception as e:
                        print(f"    (lỗi listdir: {e})")
                break
        else:
            # Không khớp rule nào — log nếu là domain game
            if self._allowed_domain(host) and filename:
                print(f"[no-match] {host} | '{filename}' không khớp rule nào")


addons = [FileReplacer()]
