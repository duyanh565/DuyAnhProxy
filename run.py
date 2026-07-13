"""
Entry point:
  $PORT      → cert_http.py  (Railway HTTP domain — trang tải cert)
  PROXY_PORT → mitmproxy     (HTTP proxy TCP — user nhập IP+port thủ công vào WiFi)
"""

import os
import shutil
import signal
import subprocess
import threading
import time

import yaml

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, "config.yaml"), "r", encoding="utf-8") as _f:
    cfg = yaml.safe_load(_f)

PROXY_PORT    = int(cfg.get("port", 9090))
PROXY_HOST    = cfg.get("proxy_host", "")
EXTERNAL_PORT = int(cfg.get("external_port", PROXY_PORT))
CERT_HOST     = cfg.get("cert_host", "")
HTTP_PORT     = int(os.environ.get("PORT", 8081))

ADDON_PATH = os.path.join(BASE_DIR, "addon.py")
CERTS_DIR  = os.path.join(BASE_DIR, "certs")
MITM_DIR   = os.path.expanduser("~/.mitmproxy")

# ── Copy cert cố định vào ~/.mitmproxy/ ─────────────────────────────────────
os.makedirs(MITM_DIR, exist_ok=True)
for fname in ["mitmproxy-ca-cert.pem", "mitmproxy-ca-cert.cer"]:
    src = os.path.join(CERTS_DIR, fname)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(MITM_DIR, fname))

key_path  = os.path.join(CERTS_DIR, "mitmproxy-ca.key")
cert_path = os.path.join(CERTS_DIR, "mitmproxy-ca-cert.pem")
if os.path.exists(key_path) and os.path.exists(cert_path):
    with open(os.path.join(MITM_DIR, "mitmproxy-ca.pem"), "wb") as out:
        for p in [key_path, cert_path]:
            with open(p, "rb") as f:
                out.write(f.read())

print("=" * 50)
print(f" Proxy      : {PROXY_HOST}:{EXTERNAL_PORT}")
print(f" Cert HTTP  : port {HTTP_PORT}")
print("=" * 50)


def _find_mitmdump() -> str:
    for c in [
        "/opt/venv/bin/mitmdump",
        os.path.expanduser("~/.local/bin/mitmdump"),
        "/usr/local/bin/mitmdump",
        "/usr/bin/mitmdump",
    ]:
        if os.path.isfile(c):
            return c
    found = shutil.which("mitmdump")
    if found:
        return found
    return "mitmdump"


def _kill_local_mitmdump():
    """Kill process mitmdump trong container này (nếu còn)."""
    my_pid = os.getpid()
    try:
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            pid = int(entry)
            if pid == my_pid:
                continue
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cmdline = f.read().decode("utf-8", errors="replace")
                if "mitmdump" in cmdline:
                    os.kill(pid, signal.SIGKILL)
                    print(f"[mitm] Đã kill mitmdump PID {pid}")
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                pass
    except Exception as e:
        print(f"[mitm] _kill_local_mitmdump: {e}")


def run_mitmproxy():
    mitmdump      = _find_mitmdump()
    restart_delay = 5

    while True:
        _kill_local_mitmdump()
        time.sleep(1)

        print(f"[mitm] Khởi động HTTP proxy tại 0.0.0.0:{PROXY_PORT}")
        try:
            result = subprocess.run([
                mitmdump,
                "--listen-host", "0.0.0.0",
                "--listen-port", str(PROXY_PORT),
                "-s", ADDON_PATH,
                "--set", "block_global=false",
                "--set", "ssl_insecure=true",
            ])
            if result.returncode == 0:
                print("[mitm] Thoát bình thường. Không restart.")
                return
            print(f"[mitm] Crash (exit {result.returncode}) — restart sau {restart_delay}s...")
        except FileNotFoundError:
            print(f"[mitm] Không tìm thấy '{mitmdump}'. Dừng.")
            return
        except Exception as e:
            print(f"[mitm] Lỗi: {e} — restart sau {restart_delay}s...")

        time.sleep(restart_delay)


threading.Thread(target=run_mitmproxy, daemon=True).start()

from cert_http import start_cert_server
print(f"[cert-http] Khởi động port {HTTP_PORT}")
start_cert_server(HTTP_PORT, PROXY_HOST, EXTERNAL_PORT, CERT_HOST)
