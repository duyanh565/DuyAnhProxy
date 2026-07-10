#!/usr/bin/env bash
set -e

echo "============================================"
echo " mitmproxy File Replacer - Khởi động..."
echo "============================================"

cd "$(dirname "$0")"
python3 run.py
