"""
Entry point chính — chạy cả cert HTTP server và mitmproxy cùng lúc.
"""

import os
import sys
import subprocess
import time
import yaml

# ── Đọc config ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cfg = yaml.safe_load(open(os.path.join(BASE_DIR, "config.yaml")))
PROXY_PORT = int(cfg.get("port", 8080))
HTTP_PORT  = int(os.environ.get("PORT", 8000))

# ── Khởi động HTTP server (cert download + health check) ────
sys.path.insert(0, BASE_DIR)
from cert_server import start_cert_server
start_cert_server(HTTP_PORT)
print(f"[run.py] HTTP server chạy tại port {HTTP_PORT}")
print(f"[run.py] Tải cert tại: http://<railway-domain>/cert.pem")

# ── Chạy mitmproxy ──────────────────────────────────────────
addon_path = os.path.join(BASE_DIR, "addon.py")
certs_dir  = os.path.join(BASE_DIR, "certs")
cmd = [
    "mitmdump",
    "--listen-host", "0.0.0.0",
    "--listen-port", str(PROXY_PORT),
    "-s", addon_path,
    "--set", f"confdir={certs_dir}",   # dùng cert đã tạo sẵn
    "--set", "block_global=false",
    "--set", "ssl_insecure=true",
]
print(f"[run.py] Khởi động mitmproxy tại port {PROXY_PORT} ...")
subprocess.run(cmd)
