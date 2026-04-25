#!/bin/bash
# macOS 用 自動実行の停止スクリプト
# 自動実行を解除します（ファイルは削除しません）

set -e
cd "$(dirname "$0")/システム（触らないでください）"

echo "自動実行を停止します..."
if [ -x ".venv/bin/python" ]; then
  .venv/bin/python scheduler.py uninstall
else
  python3 scheduler.py uninstall
fi

echo ""
read -p "Enter キーを押すとウィンドウを閉じます..."
