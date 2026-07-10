#!/usr/bin/env bash
set -e

# Đọc cổng proxy từ config.yaml (mặc định 8080)
PROXY_PORT=$(python3 -c "import yaml; cfg=yaml.safe_load(open('config.yaml')); print(cfg.get('port', 8080))")

echo "============================================"
echo " mitmproxy File Replacer - Khởi động..."
echo " Cổng proxy (TCP): $PROXY_PORT"
echo " HTTP/cert server : \$PORT (Railway tự cấp)"
echo "============================================"

# Tạo thư mục mitmproxy để sinh cert trước khi khởi động
mkdir -p ~/.mitmproxy

# Chạy mitmproxy với addon
mitmdump \
  --listen-host 0.0.0.0 \
  --listen-port "$PROXY_PORT" \
  -s addon.py \
  --set block_global=false \
  --set ssl_insecure=true
