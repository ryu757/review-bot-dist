#!/bin/bash
# macOS 用：既存の「下書き」を最新ロジックで一括再生成
# ダブルクリックで実行できます

set -e
cd "$(dirname "$0")/システム（触らないでください）"

echo "════════════════════════════════════════════════════════════"
echo "  下書きを最新ロジックで一括再生成します"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "  対象: スプレッドシートの「ステータス＝下書き」の行のみ"
echo "  影響:"
echo "    - 設定シートの『固定文末』『重点キーワード』等が反映されます"
echo "    - 手動で編集した下書きがあれば上書きされます"
echo "    - 「投稿する」「投稿済み」の行は変更されません"
echo "    - 下書き10件あたり数円〜十数円のAPI利用料が発生します"
echo ""
read -p "  続行しますか？ [y/N]: " ans
case "$ans" in
  y|Y|yes|YES) ;;
  *) echo "  中止しました。"; read -p "  Enter キーで閉じます..."; exit 0 ;;
esac

echo ""
echo "  実行中..."
echo ""
if [ -x ".venv/bin/python" ]; then
  .venv/bin/python main.py regenerate
else
  python3 main.py regenerate
fi

echo ""
read -p "Enter キーを押すとウィンドウを閉じます..."
