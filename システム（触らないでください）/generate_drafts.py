"""
スプレッドシートの「返信下書き」が空の行に対してAI下書きを生成する。

使い方:
  python generate_drafts.py

スプレッドシートに以下の列を手動入力:
  - レビュー日時
  - レビュアー
  - 評価（1〜5）
  - レビュー本文

実行すると「返信下書き」列にAI生成テキストが入り、ステータスが「下書き」になる。
"""
from datetime import datetime

from sheets_client import (
    ensure_sheet_ready,
    get_all_rows,
    _get_sheets_service,
)
from config import (
    SPREADSHEET_ID,
    SHEET_NAME,
    COL_REVIEWER,
    COL_RATING,
    COL_REVIEW_BODY,
    COL_DRAFT_REPLY,
    COL_STATUS,
    COL_UPDATED,
    STATUS_DRAFT,
)
from draft_generator import generate_draft


def run():
    ensure_sheet_ready()
    rows = get_all_rows()
    if not rows:
        print("シートにデータがありません。")
        return

    header = rows[0]
    try:
        idx_reviewer = header.index(COL_REVIEWER)
        idx_rating = header.index(COL_RATING)
        idx_body = header.index(COL_REVIEW_BODY)
        idx_draft = header.index(COL_DRAFT_REPLY)
        idx_status = header.index(COL_STATUS)
        idx_updated = header.index(COL_UPDATED)
    except ValueError as e:
        print(f"ヘッダーが不正です: {e}")
        return

    sheets = _get_sheets_service()
    count = 0

    for i, row in enumerate(rows[1:], start=2):
        # 行の長さを補完
        while len(row) <= max(idx_draft, idx_status, idx_updated):
            row.append("")

        draft = (row[idx_draft] or "").strip()
        rating = (row[idx_rating] or "").strip()
        reviewer = (row[idx_reviewer] or "").strip()
        body = (row[idx_body] or "").strip()

        # 下書きが既にある、または評価がない行はスキップ
        if draft or not rating:
            continue

        print(f"行{i}: {reviewer} (★{rating}) の下書きを生成中...")
        reply = generate_draft(reviewer, rating, body)

        # 下書き・ステータス・更新日時を書き込む
        draft_col = chr(ord("A") + idx_draft)
        updated_col = chr(ord("A") + idx_updated)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # F列(下書き), G列(ステータス), H列(更新日時) をまとめて更新
        range_str = f"'{SHEET_NAME}'!{draft_col}{i}:{updated_col}{i}"
        body_data = {"values": [[reply, STATUS_DRAFT, now]]}
        sheets.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_str,
            valueInputOption="USER_ENTERED",
            body=body_data,
        ).execute()

        print(f"  → 下書き生成完了")
        count += 1

    print(f"\n{count} 件の下書きを生成しました。")


if __name__ == "__main__":
    run()
