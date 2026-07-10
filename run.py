"""
Entry point:
  $PORT  → cert_http.py  (Railway HTTP domain → HTTPS tự động → tải cert)
  8081   → mitmproxy     (Railway TCP proxy 56020 → 8081 → proxy iPhone)
"""

import os
import shutil
import subprocess
import threading
import time
import yaml

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
cfg        = yaml.safe_load(open(os.path.join(BASE_DIR, "config.yaml")))
CERT_HOST  = cfg.get("cert_host", "")
PROXY_PORT = int(cfg.get("port", 8081))          # TCP proxy port (mitmproxy)
HTTP_PORT  = int(os.environ.get("PORT", 8081))   # Railway HTTP domain port
ADDON_PATH = os.path.join(BASE_DIR, "addon.py")
CERTS_DIR  = os.path.join(BASE_DIR, "certs")
MITM_DIR   = os.path.expanduser("~/.mitmproxy")

# ── 1. Copy cert vào ~/.mitmproxy/ để mitmproxy dùng cert cố định ─────────────

os.makedirs(MITM_DIR, exist_ok=True)
for fname in ["mitmproxy-ca-cert.pem", "mitmproxy-ca-cert.cer"]:
    src = os.path.join(CERTS_DIR, fname)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(MITM_DIR, fname))

# mitmproxy-ca.pem = private key + cert nối lại
key_path  = os.path.join(CERTS_DIR, "mitmproxy-ca.key")
cert_path = os.path.join(CERTS_DIR, "mitmproxy-ca-cert.pem")
if os.path.exists(key_path) and os.path.exists(cert_path):
    with open(os.path.join(MITM_DIR, "mitmproxy-ca.pem"), "wb") as out:
        out.write(open(key_path, "rb").read())
        out.write(open(cert_path, "rb").read())

print("============================================")
print(f" Cert HTTP  : port {HTTP_PORT}  (Railway domain → HTTPS)")
print(f" mitmproxy  : port {PROXY_PORT}  (Railway TCP proxy 56020)")
if CERT_HOST:
    print(f" Proxy host : {CERT_HOST}:{PROXY_PORT}")
print("============================================")

# ── 2. Khởi động cert HTTP server ─────────────────────────────────────────────

from cert_http import start_cert_server_thread
start_cert_server_thread(HTTP_PORT, CERT_HOST, PROXY_PORT)

# ── 3. Khởi động mitmproxy (blocking) ─────────────────────────────────────────

print(f"[mitm] Khởi động tại 0.0.0.0:{PROXY_PORT}")
subprocess.run([
    "mitmdump",
    "--listen-host", "0.0.0.0",
    "--listen-port", str(PROXY_PORT),
    "-s", ADDON_PATH,
    "--set", "block_global=false",
    "--set", "ssl_insecure=true",
])
