"""
mitmproxy addon — tự động thay file game theo rules trong config.yaml.
"""

import hashlib
import os
import time
import yaml
from mitmproxy import http

CONFIG_PATH      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")
REPLACEMENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "replacements")

# Theo dõi số lần mỗi file bị request (để phát hiện re-download)
_request_count: dict[str, int] = {}
_last_replaced: dict[str, float] = {}


class FileReplacer:
    def __init__(self):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        self.rules   = config.get("rules", [])
        self.allowed = config.get("allowed_domains", [])

        print(f"[addon] REPLACEMENTS_DIR = {REPLACEMENTS_DIR}")
        print(f"[addon] Đã tải {len(self.rules)} rule(s).")
        for r in self.rules:
            rpath  = os.path.join(REPLACEMENTS_DIR, r.get("replace_with", ""))
            exists = os.path.exists(rpath)
            size   = os.path.getsize(rpath) if exists else 0
            md5    = ""
            if exists:
                with open(rpath, "rb") as f:
                    md5 = hashlib.md5(f.read()).hexdigest()
            print(f"  [{r.get('app','')}] match='{r.get('match','?')}' "
                  f"→ exists={exists} size={size} md5={md5}")

    def _allowed_domain(self, host: str) -> bool:
        if not self.allowed:
            return True
        return any(host == d or host.endswith("." + d) for d in self.allowed)

    def _match_rule(self, filename: str, url: str):
        """Trả về rule đầu tiên khớp với filename hoặc url."""
        for rule in self.rules:
            match = rule.get("match", "")
            if match and (match in filename or match in url):
                return rule
        return None

    def request(self, flow: http.HTTPFlow) -> None:
        host = flow.request.host
        url  = flow.request.pretty_url

        if not any(kw in host for kw in ["garena", "freefire", "gmc"]):
            return

        full_url_no_qs = url.split("?")[0]
        filename = full_url_no_qs.split("/")[-1]

        # Đếm số lần request — phát hiện re-download
        _request_count[filename] = _request_count.get(filename, 0) + 1
        count = _request_count[filename]

        if count == 1:
            print(f"[req] {flow.request.method} {url[:120]}")
        else:
            # Đây là re-download — game đang tải lại file!
            rule = self._match_rule(filename, full_url_no_qs)
            tag  = " ← FILE NÀY ĐÃ ĐƯỢC THAY" if rule else ""
            print(f"[RE-DOWNLOAD #{count}]{tag} {host} | '{filename}'")
            if rule:
                print(f"  ⚠️  Game đang re-download file đã bị thay — "
                      f"có thể hash không khớp với assetindexer!")

    def response(self, flow: http.HTTPFlow) -> None:
        if flow.response is None:
            return

        host         = flow.request.host
        full_url     = flow.request.pretty_url.split("?")[0]
        filename     = full_url.split("/")[-1]
        orig_size    = len(flow.response.content)

        is_game = any(kw in host for kw in ["garena", "freefire", "gmc"])
        if is_game:
            print(f"[res] {host} | '{filename}' | status={flow.response.status_code} "
                  f"| orig_size={orig_size}")

        if not self._allowed_domain(host):
            if is_game:
                print(f"[skip] domain không trong allowed_domains: {host}")
            return

        rule = self._match_rule(filename, full_url)
        if not rule:
            if is_game and self._allowed_domain(host) and filename:
                print(f"[no-match] '{filename}' không khớp rule nào")
            return

        replace_with = rule.get("replace_with", "")
        if not replace_with:
            print(f"[!] Rule thiếu 'replace_with': {rule}")
            return

        path = os.path.join(REPLACEMENTS_DIR, replace_with)
        print(f"[match] Khớp rule | filename='{filename}' | file thay: {path}")

        if not os.path.exists(path):
            print(f"[!] File thay KHÔNG TỒN TẠI: {path}")
            print(f"[!] Các file trong {REPLACEMENTS_DIR}:")
            for fn in os.listdir(REPLACEMENTS_DIR):
                print(f"    - {fn}")
            return

        try:
            with open(path, "rb") as f:
                content = f.read()

            new_size = len(content)
            new_md5  = hashlib.md5(content).hexdigest()

            flow.response.content     = content
            flow.response.status_code = 200
            for h in ["Content-Encoding", "Transfer-Encoding",
                      "Cache-Control", "ETag", "Last-Modified",
                      "Expires", "Age"]:
                flow.response.headers.pop(h, None)
            flow.response.headers["Content-Length"] = str(new_size)
            flow.response.headers["Cache-Control"]  = "no-store, no-cache, must-revalidate"
            flow.response.headers.setdefault("Content-Type", "application/octet-stream")

            _last_replaced[filename] = time.time()

            print(f"[✓] ĐÃ THAY: '{filename}'")
            print(f"    orig_size={orig_size}  →  new_size={new_size}")
            print(f"    new_md5={new_md5}")
            if orig_size != new_size:
                print(f"    ⚠️  Kích thước khác nhau — nếu game hash-verify "
                      f"assetindexer thì sẽ bị reject!")

        except OSError as e:
            print(f"[!] Lỗi đọc file thay: {path} — {e}")


addons = [FileReplacer()]
