"""
Entry point:
  1. Khởi động mitmproxy ở 127.0.0.1:8081 (nội bộ)
  2. Khởi động TCP router ở 0.0.0.0:8080 (Railway expose)
     • Direct request  → phục vụ trang tải cert
     • Proxy request   → chuyển tiếp sang mitmproxy:8081
"""

import asyncio
import os
import subprocess
import threading
import time
import yaml

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
cfg        = yaml.safe_load(open(os.path.join(BASE_DIR, "config.yaml")))
PROXY_PORT = int(cfg.get("port", 8080))   # port Railway expose (và người dùng nhập vào iPhone)
MITM_PORT  = PROXY_PORT + 1               # port mitmproxy nội bộ (không expose ra ngoài)
CERT_HOST  = cfg.get("cert_host", "")
ADDON_PATH = os.path.join(BASE_DIR, "addon.py")

# ── 1. Khởi động mitmproxy trong thread riêng ─────────────────────────────────

def run_mitmproxy():
    print(f"[mitm] Khởi động mitmproxy tại 127.0.0.1:{MITM_PORT}")
    subprocess.run([
        "mitmdump",
        "--listen-host", "127.0.0.1",
        "--listen-port", str(MITM_PORT),
        "-s", ADDON_PATH,
        "--set", "block_global=false",
        "--set", "ssl_insecure=true",
    ])

t = threading.Thread(target=run_mitmproxy, daemon=True)
t.start()

# Chờ mitmproxy sẵn sàng trước khi router bắt đầu nhận kết nối
time.sleep(3)

# ── 2. Khởi động TCP router ───────────────────────────────────────────────────

from router import start_router   # import sau khi mitmproxy đã start

print("============================================")
print(f" Railway port : {PROXY_PORT}  (nhập vào iPhone)")
if CERT_HOST:
    print(f" Tải cert     : http://{CERT_HOST}:{PROXY_PORT}/")
print("============================================")

asyncio.run(start_router("0.0.0.0", PROXY_PORT, CERT_HOST, PROXY_PORT))
