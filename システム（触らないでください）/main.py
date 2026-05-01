"""
Google マップのレビュー → スプレッドシートに下書き → 確認後に投稿する処理のエントリポイント。

使い方:
  python main.py login        … 初回ログイン（ブラウザが開く）
  python main.py sync         … 新着レビューをシートに下書きとして追加
  python main.py post         … 「投稿する」の行を実際に Google に投稿
  python main.py run          … sync のあと post を実行（推奨: 定期実行用）
  python main.py regenerate   … 既存の「下書き」を最新ロジックで一括再生成
  python main.py fix-dates    … レビュー日時を再取得して修正
"""
import sys

# 起動時に GitHub 上の新版を自動取得（無効: DISABLE_AUTO_UPDATE=1）
try:
    import auto_update
    if auto_update.check_and_update_silent():
        auto_update.restart_self()
except ImportError:
    pass

from browser_client import login_interactive
from sync_reviews import sync_new_reviews_to_sheet, fix_review_dates, regenerate_drafts
from post_replies import post_pending_replies


def main() -> None:
    cmd = (sys.argv[1:] or ["run"])[0].lower()

    if cmd == "login":
        login_interactive()
    elif cmd == "sync":
        n = sync_new_reviews_to_sheet()
        print(f"レビュー下書きを {n} 件追加しました。")
    elif cmd == "post":
        ok, ng = post_pending_replies()
        print(f"投稿: 成功 {ok} 件、失敗 {ng} 件")
    elif cmd == "run":
        n = sync_new_reviews_to_sheet()
        print(f"レビュー下書きを {n} 件追加しました。")
        ok, ng = post_pending_replies()
        print(f"投稿: 成功 {ok} 件、失敗 {ng} 件")
    elif cmd == "regenerate":
        ok, ng = regenerate_drafts()
        print(f"再生成: 成功 {ok} 件、失敗 {ng} 件")
    elif cmd == "fix-dates":
        n = fix_review_dates()
        print(f"レビュー日時を {n} 件修正しました。")
    else:
        print("使い方: python main.py [login|sync|post|run|regenerate|fix-dates]")
        sys.exit(1)


if __name__ == "__main__":
    main()
