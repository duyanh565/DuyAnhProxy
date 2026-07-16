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

print(f"[debug] $PORT từ Railway = {os.environ.get('PORT', '(không có, dùng 8081)')}")
print(f"[debug] PROXY_PORT (mitmproxy) = {PROXY_PORT}")
print(f"[debug] HTTP_PORT  (cert web)  = {HTTP_PORT}")

ADDON_PATH = os.path.join(BASE_DIR, "addon.py")
CERTS_DIR  = BASE_DIR
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


import socket as _socket


def _force_free_port(port: int):
    """Kill bất kỳ tiến trình nào đang giữ port bằng ss."""
    try:
        import re
        out = subprocess.check_output(
            ["ss", "-tlnp", f"sport = :{port}"], text=True, stderr=subprocess.DEVNULL
        )
        for pid_str in re.findall(r"pid=(\d+)", out):
            pid = int(pid_str)
            try:
                os.kill(pid, signal.SIGKILL)
                print(f"[mitm] Force-killed PID {pid} giữ port {port}")
            except Exception:
                pass
    except Exception:
        pass
    time.sleep(1)


def _wait_port_free(port: int, timeout: int = 30) -> bool:
    """Chờ đến khi port không còn bị chiếm (tối đa timeout giây)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            s.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            s.bind(("0.0.0.0", port))
            s.close()
            return True
        except OSError:
            time.sleep(2)
    return False


def _kill_group(pgid: int):
    """Kill toàn bộ process group (bao gồm tiến trình con của mitmproxy)."""
    try:
        os.killpg(pgid, signal.SIGKILL)
        print(f"[mitm] Đã kill process group {pgid}")
    except (ProcessLookupError, PermissionError):
        pass


def run_mitmproxy():
    mitmdump      = _find_mitmdump()
    restart_delay = 5

    while True:
        _force_free_port(PROXY_PORT)
        if not _wait_port_free(PROXY_PORT, timeout=15):
            print(f"[mitm] Port {PROXY_PORT} vẫn bận sau force-kill — thử khởi động thẳng...")

        print(f"[mitm] Khởi động HTTP proxy tại 0.0.0.0:{PROXY_PORT}")
        proc = None
        try:
            proc = subprocess.Popen(
                [
                    mitmdump,
                    "--listen-host", "0.0.0.0",
                    "--listen-port", str(PROXY_PORT),
                    "-s", ADDON_PATH,
                    "--set", "block_global=false",
                    "--set", "ssl_insecure=true",
                    # Chỉ MITM CDN asset — login/game server đi thẳng không bị chặn
                    "--allow-hosts",
                    r"(cdn\.freefiremobile\.com|res\.cdn\.garena\.com|static\.cdn\.garena\.com)",
                ],
                preexec_fn=os.setsid,  # tạo process group riêng
            )
            returncode = proc.wait()
            if returncode == 0:
                print("[mitm] Thoát bình thường. Không restart.")
                return
            print(f"[mitm] Crash (exit {returncode}) — restart sau {restart_delay}s...")
        except FileNotFoundError:
            print(f"[mitm] Không tìm thấy '{mitmdump}'. Dừng.")
            return
        except Exception as e:
            print(f"[mitm] Lỗi: {e} — restart sau {restart_delay}s...")
        finally:
            if proc is not None:
                try:
                    _kill_group(os.getpgid(proc.pid))
                except Exception:
                    pass

        time.sleep(restart_delay)


threading.Thread(target=run_mitmproxy, daemon=True).start()

from cert_http import start_cert_server
print(f"[cert-http] Khởi động port {HTTP_PORT}")
try:
    start_cert_server(HTTP_PORT, PROXY_HOST, EXTERNAL_PORT, CERT_HOST)
except Exception as e:
    print(f"[cert-http] Crash: {e}. Giữ process để proxy tiếp tục chạy.")
    while True:
        time.sleep(3600)