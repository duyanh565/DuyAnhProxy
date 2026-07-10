"""
Entry point — khởi động mitmproxy.
Cert được serve trực tiếp qua proxy tại http://cert.download/
"""

import os
import sys
import subprocess
import yaml

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
cfg = yaml.safe_load(open(os.path.join(BASE_DIR, "config.yaml")))
PROXY_PORT = int(cfg.get("port", 8080))

addon_path = os.path.join(BASE_DIR, "addon.py")

print("============================================")
print(f" mitmproxy khởi động tại port {PROXY_PORT}")
print(f" Cài proxy xong → mở Safari → vào http://cert.download/")
print(f" Tải cert tại đó rồi cài lên iPhone")
print("============================================")

subprocess.run([
    "mitmdump",
    "--listen-host", "0.0.0.0",
    "--listen-port", str(PROXY_PORT),
    "-s", addon_path,
    "--set", "block_global=false",
    "--set", "ssl_insecure=true",
])
