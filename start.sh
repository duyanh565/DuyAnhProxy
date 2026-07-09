#!/usr/bin/env bash
set -e

# Đọc cổng từ config.yaml (trường "port:"), mặc định 8080 nếu không có
PROXY_PORT=$(python3 -c "import yaml; cfg=yaml.safe_load(open('config.yaml')); print(cfg.get('port', 8080))")

echo "============================================"
echo " mitmproxy File Replacer - Khởi động..."
echo " Đang lắng nghe tại: 0.0.0.0:$PROXY_PORT"
echo "============================================"
echo ""
echo " → Nhập vào iOS:"
echo "   Server: <IP hoặc hostname Railway TCP>"
echo "   Cổng  : $PROXY_PORT"
echo "============================================"

mitmdump \
  --listen-host 0.0.0.0 \
  --listen-port "$PROXY_PORT" \
  --scripts addon.py \
  --set block_global=false \
  --ssl-insecure
