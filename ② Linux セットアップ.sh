#!/bin/bash
# Linux 用セットアップ起動スクリプト
# ターミナルで実行してください: bash setup.sh

set -e
cd "$(dirname "$0")/システム（触らないでください）"

echo "╔════════════════════════════════════════════════════════════╗"
echo "║   Google レビュー自動返信システム — セットアップ開始       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ Python 3 がインストールされていません。"
  echo ""
  echo "以下のコマンドでインストールしてください："
  echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
  echo "  Fedora/RHEL:   sudo dnf install python3 python3-pip"
  echo ""
  exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✓ Python ${PY_VERSION} を検出しました"
echo ""

python3 setup_wizard.py
