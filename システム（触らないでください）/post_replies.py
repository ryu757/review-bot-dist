"""
スプレッドシートで「投稿する」になっている行を取得し、
ブラウザ操作で Google マップに返信を投稿してステータスを「投稿済み」に更新する。
"""
from __future__ import annotations

import time

from config import STATUS_POSTED
from browser_client import post_reply
from sheets_client import get_rows_to_post, set_row_status_and_updated

try:
    import notify  # type: ignore
except ImportError:
    notify = None  # type: ignore


def post_pending_replies() -> tuple[int, int]:
    """
    「投稿する」の行を順に投稿する。
    返り値: (成功数, 失敗数)
    """
    to_post = get_rows_to_post()
    ok, ng = 0, 0
    for row_index, review_id, draft_comment in to_post:
        print(f"  投稿中 (行{row_index}): {review_id[:30]}...")
        try:
            success = post_reply(review_id, draft_comment)
            if success:
                set_row_status_and_updated(row_index, STATUS_POSTED)
                ok += 1
                print(f"    → 投稿成功")
            else:
                ng += 1
                print(f"    → 投稿失敗")
                if notify:
                    notify.notify(
                        "WARN",
                        "返信投稿失敗 (post)",
                        "post_reply() が False を返しました。",
                        review_id=review_id[:50],
                        row_index=row_index,
                    )
        except Exception as e:
            print(f"    → エラー: {e}")
            ng += 1
            if notify:
                notify.notify_exception(
                    "返信投稿で例外 (post)",
                    e,
                    review_id=review_id[:50],
                    row_index=row_index,
                )
        # 連続投稿を避けるため少し待つ
        if to_post.index((row_index, review_id, draft_comment)) < len(to_post) - 1:
            time.sleep(5)
    return ok, ng
