"""
Entry point:
  $PORT      → cert_http.py  (Railway HTTP domain — trang tải cert)
  PROXY_PORT → mitmproxy     (HTTP proxy TCP — user nhập IP+port thủ công vào WiFi)
"""

import glob
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

PROXY_PORT    = int(cfg.get("port", 3636))
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


# ── Giải phóng port bằng Python thuần — không dùng fuser/pkill ──────────────

def _find_pid_by_inode(inode: str):
    """Tìm PID đang giữ socket inode."""
    for fd_path in glob.glob("/proc/[0-9]*/fd/*"):
        try:
            if f"socket:[{inode}]" in os.readlink(fd_path):
                return int(fd_path.split("/")[2])
        except OSError:
            pass
    return None


def _free_port(port: int):
    """Kill process đang giữ port qua /proc/net/tcp (không cần fuser/pkill)."""
    hex_port = format(port, "04X")
    killed = False
    try:
        with open("/proc/net/tcp") as f:
            for line in f.readlines()[1:]:          # bỏ header
                parts = line.split()
                if len(parts) < 10:
                    continue
                local_port_hex = parts[1].split(":")[1].upper()
                if local_port_hex != hex_port:
                    continue
                inode = parts[9]
                pid = _find_pid_by_inode(inode)
                if pid and pid != os.getpid():
                    try:
                        os.kill(pid, signal.SIGKILL)
                        print(f"[mitm] Đã SIGKILL PID {pid} (port {port})")
                        killed = True
                    except ProcessLookupError:
                        pass
    except Exception as e:
        print(f"[mitm] _free_port: {e}")

    if killed:
        time.sleep(2)   # chờ OS giải phóng socket


def run_mitmproxy():
    mitmdump      = _find_mitmdump()
    restart_delay = 8

    while True:
        print(f"[mitm] Giải phóng port {PROXY_PORT}...")
        _free_port(PROXY_PORT)

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
