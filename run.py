"""
Entry point:
  $PORT  → cert_http.py  (Railway HTTP domain → HTTPS → tải cert & cấu hình proxy)
  3636   → mitmproxy     (Railway TCP proxy 56020 → 3636 → proxy iPhone)

Cert server chạy ở main thread để Railway health-check pass.
mitmproxy chạy ở background thread.
"""

import os
import shutil
import subprocess
import threading

import yaml

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Đọc config
with open(os.path.join(BASE_DIR, "config.yaml"), "r", encoding="utf-8") as _f:
    cfg = yaml.safe_load(_f)

CERT_HOST     = cfg.get("cert_host", "")
PROXY_PORT    = int(cfg.get("port", 3636))
PROXY_HOST    = cfg.get("proxy_host", CERT_HOST)          # hostname iPhone dùng để kết nối
EXTERNAL_PORT = int(cfg.get("external_port", PROXY_PORT))  # port iPhone nhập vào WiFi

# Railway gán $PORT cho HTTP domain — cert server luôn bind vào đây
# KHÔNG dùng PROXY_PORT cho $PORT, hai cái này độc lập nhau
# BUG FIX: bỏ logic collision sai (nếu PORT==PROXY_PORT thì đổi sang 8081
# nhưng Railway vẫn health-check $PORT → timeout crash loop)
HTTP_PORT = int(os.environ.get("PORT", 8081))

ADDON_PATH = os.path.join(BASE_DIR, "addon.py")
CERTS_DIR  = os.path.join(BASE_DIR, "certs")
MITM_DIR   = os.path.expanduser("~/.mitmproxy")

# ── Copy cert cố định vào ~/.mitmproxy/ ───────────────────────────────────────

os.makedirs(MITM_DIR, exist_ok=True)
for fname in ["mitmproxy-ca-cert.pem", "mitmproxy-ca-cert.cer"]:
    src = os.path.join(CERTS_DIR, fname)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(MITM_DIR, fname))

key_path  = os.path.join(CERTS_DIR, "mitmproxy-ca.key")
cert_path = os.path.join(CERTS_DIR, "mitmproxy-ca-cert.pem")
if os.path.exists(key_path) and os.path.exists(cert_path):
    with open(os.path.join(MITM_DIR, "mitmproxy-ca.pem"), "wb") as out:
        with open(key_path, "rb") as kf:
            out.write(kf.read())
        with open(cert_path, "rb") as cf:
            out.write(cf.read())

print("============================================")
print(f" Cert HTTP  : port {HTTP_PORT}  → https://{CERT_HOST}/")
print(f" mitmproxy  : port {PROXY_PORT}  → TCP proxy 56020")
print("============================================")

# ── mitmproxy chạy trong background thread ────────────────────────────────────

def _find_mitmdump() -> str:
    """
    Tìm mitmdump trong PATH và các vị trí pip thường cài vào.
    Trả về đường dẫn tuyệt đối nếu tìm thấy, ngược lại trả về 'mitmdump'.
    """
    import shutil as _sh
    found = _sh.which("mitmdump")
    if found:
        return found
    # pip install --user thường cài vào ~/.local/bin
    candidates = [
        os.path.expanduser("~/.local/bin/mitmdump"),
        "/usr/local/bin/mitmdump",
        "/usr/bin/mitmdump",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return "mitmdump"   # thử luôn, sẽ bắt lỗi bên dưới nếu không có


def run_mitmproxy():
    """Chạy mitmdump và tự động restart nếu bị crash."""
    import time
    mitmdump = _find_mitmdump()
    print(f"[mitm] Sử dụng: {mitmdump}")

    restart_delay = 5  # giây chờ trước khi restart
    while True:
        print(f"[mitm] Khởi động tại 0.0.0.0:{PROXY_PORT}")
        try:
            subprocess.run([
                mitmdump,
                "--listen-host", "0.0.0.0",
                "--listen-port", str(PROXY_PORT),
                "-s", ADDON_PATH,
                "--set", "block_global=false",
                "--set", "ssl_insecure=true",
            ])
            print(f"[mitm] Thoát bình thường — restart sau {restart_delay}s...")
        except FileNotFoundError:
            print(f"[mitm] LỖI: Không tìm thấy '{mitmdump}'. Dừng hẳn.")
            return   # mitmdump không tồn tại → không restart vô hạn
        except Exception as e:
            print(f"[mitm] LỖI: {e} — restart sau {restart_delay}s...")
        time.sleep(restart_delay)


threading.Thread(target=run_mitmproxy, daemon=True).start()

# ── Cert HTTP server chạy ở main thread (blocking) ────────────────────────────
# Railway health-check thấy process còn sống qua endpoint /health trên $PORT.

from cert_http import start_cert_server
print(f"[cert-http] Khởi động tại 0.0.0.0:{HTTP_PORT}")
start_cert_server(HTTP_PORT, CERT_HOST, PROXY_HOST, EXTERNAL_PORT)
