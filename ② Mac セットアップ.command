#!/bin/bash
# macOS 用ワンクリック起動スクリプト
# Finder でダブルクリックすると Terminal が開いてセットアップが始まります

set -e
cd "$(dirname "$0")/システム（触らないでください）"

clear
echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Google レビュー自動返信システム — セットアップ開始       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ Python 3 がインストールされていません。"
  echo ""
  echo "以下のページからインストーラをダウンロードしてください："
  echo "  https://www.python.org/downloads/"
  echo ""
  echo "インストール後、再度このスクリプトをダブルクリックしてください。"
  echo ""
  read -p "Enter キーを押すと閉じます..."
  exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓ Python ${PY_VERSION} を検出しました"
echo ""

python3 setup_wizard.py
RC=$?

echo ""
echo "════════════════════════════════════════════════════════════"
read -p "Enter キーを押すとウィンドウを閉じます..."
exit $RC
