"""Google スプレッドシート操作（配布版・日本語専用・設定シート対応）"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import httplib2
from googleapiclient.discovery import build

from auth import get_credentials
from config import (
    SPREADSHEET_ID,
    SHEET_NAME,
    SHEET_HEADERS,
    CONFIG_SHEET_NAME,
    CONFIG_HEADERS,
    DEFAULT_CONFIG_ROWS,
    CONFIG_KEY_BUSINESS_NAME,
    CONFIG_KEY_INDUSTRY,
    CONFIG_KEY_WEBSITE_URL,
    COL_REVIEW_DATE,
    COL_REVIEW_NAME,
    COL_REVIEWER,
    COL_RATING,
    COL_REVIEW_BODY,
    COL_DRAFT_REPLY,
    COL_STATUS,
    COL_UPDATED,
    STATUS_DRAFT,
    STATUS_TO_POST,
    STATUS_POSTED,
)

_CACHED_CONFIG: dict | None = None


def _get_sheets_service():
    creds = get_credentials()
    from google_auth_httplib2 import AuthorizedHttp
    http = AuthorizedHttp(creds, http=httplib2.Http(timeout=60))
    return build("sheets", "v4", http=http)


def create_new_spreadsheet(title: str = "Google レビュー返信ボット") -> tuple[str, str]:
    """新規スプレッドシートを作成し、(spreadsheet_id, url) を返す。"""
    sheets = _get_sheets_service().spreadsheets()
    body = {"properties": {"title": title}}
    resp = sheets.create(body=body, fields="spreadsheetId,spreadsheetUrl").execute()
    return resp["spreadsheetId"], resp["spreadsheetUrl"]


def get_config_sheet_url() -> str:
    """設定シートを直接開けるURLを返す（gid指定）。"""
    if not SPREADSHEET_ID:
        return ""
    sheets = _get_sheets_service().spreadsheets()
    meta = sheets.get(spreadsheetId=SPREADSHEET_ID).execute()
    config_gid = None
    for s in meta.get("sheets", []):
        if s["properties"]["title"] == CONFIG_SHEET_NAME:
            config_gid = s["properties"]["sheetId"]
            break
    base_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"
    return f"{base_url}#gid={config_gid}" if config_gid is not None else base_url


def _column_letter(index: int) -> str:
    return chr(ord("A") + index)


def _last_column_letter() -> str:
    return _column_letter(len(SHEET_HEADERS) - 1)


def ensure_sheet_ready():
    """レビュー返信シートと設定シートの存在を確認し、必要なら作成する。
    ステータス列にプルダウン（データの入力規則）も自動設定する。
    """
    if not SPREADSHEET_ID:
        raise ValueError("環境変数 SPREADSHEET_ID を設定してください。")
    sheets = _get_sheets_service().spreadsheets()
    meta = sheets.get(spreadsheetId=SPREADSHEET_ID).execute()
    sheet_names = [s["properties"]["title"] for s in meta.get("sheets", [])]

    add_requests = []
    if SHEET_NAME not in sheet_names:
        add_requests.append({"addSheet": {"properties": {"title": SHEET_NAME}}})
    if CONFIG_SHEET_NAME not in sheet_names:
        add_requests.append({"addSheet": {"properties": {"title": CONFIG_SHEET_NAME}}})
    if add_requests:
        sheets.batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"requests": add_requests},
        ).execute()

    # レビュー返信シートのヘッダー
    last_col = _last_column_letter()
    _get_sheets_service().spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{SHEET_NAME}'!A1:{last_col}1",
        valueInputOption="USER_ENTERED",
        body={"values": [SHEET_HEADERS]},
    ).execute()

    # ステータス列にプルダウン（データの入力規則）を設定
    review_sheet_id = None
    meta2 = _get_sheets_service().spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    for s in meta2.get("sheets", []):
        if s["properties"]["title"] == SHEET_NAME:
            review_sheet_id = s["properties"]["sheetId"]
            break
    if review_sheet_id is not None:
        status_col_idx = SHEET_HEADERS.index(COL_STATUS)
        _get_sheets_service().spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={
                "requests": [{
                    "setDataValidation": {
                        "range": {
                            "sheetId": review_sheet_id,
                            "startRowIndex": 1,      # ヘッダー除く
                            "endRowIndex": 10000,    # 余裕を持って
                            "startColumnIndex": status_col_idx,
                            "endColumnIndex": status_col_idx + 1,
                        },
                        "rule": {
                            "condition": {
                                "type": "ONE_OF_LIST",
                                "values": [
                                    {"userEnteredValue": STATUS_DRAFT},
                                    {"userEnteredValue": STATUS_TO_POST},
                                    {"userEnteredValue": STATUS_POSTED},
                                ],
                            },
                            "showCustomUi": True,
                            "strict": False,
                        },
                    }
                }]
            },
        ).execute()

    # 設定シートの初期化／マイグレーション
    existing = _get_sheets_service().spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{CONFIG_SHEET_NAME}'!A1:B20",
    ).execute().get("values", [])
    if not existing:
        # 新規作成: ヘッダー + デフォルト全行を書き込み
        _get_sheets_service().spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"'{CONFIG_SHEET_NAME}'!A1:B{1 + len(DEFAULT_CONFIG_ROWS)}",
            valueInputOption="USER_ENTERED",
            body={"values": [CONFIG_HEADERS] + DEFAULT_CONFIG_ROWS},
        ).execute()
    else:
        # 既存シート: 不足している項目を末尾に追加（既存値は保護）
        existing_keys = {row[0].strip() for row in existing[1:] if row and row[0]}
        missing_rows = [r for r in DEFAULT_CONFIG_ROWS if r[0] not in existing_keys]
        if missing_rows:
            _get_sheets_service().spreadsheets().values().append(
                spreadsheetId=SPREADSHEET_ID,
                range=f"'{CONFIG_SHEET_NAME}'!A:B",
                valueInputOption="USER_ENTERED",
                body={"values": missing_rows},
            ).execute()


def get_business_config() -> dict:
    """設定シートから事業情報を読み取って dict で返す（プロセス内キャッシュあり）。"""
    global _CACHED_CONFIG
    if _CACHED_CONFIG is not None:
        return _CACHED_CONFIG
    if not SPREADSHEET_ID:
        return {}
    rows = _get_sheets_service().spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{CONFIG_SHEET_NAME}'!A1:B20",
    ).execute().get("values", [])
    out: dict = {}
    for row in rows[1:]:
        if len(row) >= 2 and row[0]:
            out[row[0].strip()] = (row[1] or "").strip()
    _CACHED_CONFIG = out
    return out


def set_business_config(business_name: str = "", industry: str = "", website_url: str = "") -> None:
    """設定シートに事業情報を書き込む（セットアップ時に使用）。"""
    if not SPREADSHEET_ID:
        return
    rows = [
        CONFIG_HEADERS,
        [CONFIG_KEY_BUSINESS_NAME, business_name],
        [CONFIG_KEY_INDUSTRY, industry],
        [CONFIG_KEY_WEBSITE_URL, website_url],
    ]
    _get_sheets_service().spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{CONFIG_SHEET_NAME}'!A1:B{len(rows)}",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()
    global _CACHED_CONFIG
    _CACHED_CONFIG = None  # 次回再読み込み


def append_draft_row(row: list[Any]) -> None:
    """1行分のデータをシートの末尾に追加。

    insertDataOption は指定しない（=OVERWRITE）。INSERT_ROWS だと既存セルの
    データ検証（プルダウン）が新行に継承されないため。OVERWRITE なら既存の
    空セル（検証付き）に書き込むので、ステータス列のプルダウンが維持される。
    """
    if not SPREADSHEET_ID:
        raise ValueError("環境変数 SPREADSHEET_ID を設定してください。")
    _get_sheets_service().spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{SHEET_NAME}'!A:A",
        valueInputOption="RAW",
        body={"values": [row]},
    ).execute()


def get_all_rows() -> list[list[Any]]:
    """ヘッダー含む全行を取得。"""
    if not SPREADSHEET_ID:
        return []
    last_col = _last_column_letter()
    result = _get_sheets_service().spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"'{SHEET_NAME}'!A:{last_col}",
    ).execute()
    return result.get("values", [])


def get_rows_to_post() -> list[tuple[int, str, str]]:
    """「投稿する」の行を取得。返り値: [(行番号, review_id, draft), ...]"""
    rows = get_all_rows()
    if not rows:
        return []
    header = rows[0]
    try:
        col_status_idx = header.index(COL_STATUS)
        col_review_name_idx = header.index(COL_REVIEW_NAME)
        col_draft_idx = header.index(COL_DRAFT_REPLY)
    except ValueError:
        return []
    out = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) <= max(col_status_idx, col_review_name_idx, col_draft_idx):
            continue
        if row[col_status_idx].strip() != STATUS_TO_POST:
            continue
        review_name = (row[col_review_name_idx] or "").strip()
        draft = (row[col_draft_idx] or "").strip()
        if review_name and draft:
            out.append((i, review_name, draft))
    return out


def set_row_status_and_updated(row_index_1based: int, status: str) -> None:
    """指定行のステータスと更新日時を更新。"""
    if not SPREADSHEET_ID:
        return
    header = get_all_rows()[0]
    col_status_idx = header.index(COL_STATUS)
    col_updated_idx = header.index(COL_UPDATED)
    status_col = _column_letter(col_status_idx)
    updated_col = _column_letter(col_updated_idx)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    range_str = f"'{SHEET_NAME}'!{status_col}{row_index_1based}:{updated_col}{row_index_1based}"
    _get_sheets_service().spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=range_str,
        valueInputOption="USER_ENTERED",
        body={"values": [[status, now]]},
    ).execute()


def get_pending_rows_for_display() -> list[dict]:
    """「下書き」または「投稿する」の行を表示用に取得。"""
    rows = get_all_rows()
    if not rows:
        return []
    header = rows[0]
    try:
        idx_date = header.index(COL_REVIEW_DATE)
        idx_name = header.index(COL_REVIEW_NAME)
        idx_reviewer = header.index(COL_REVIEWER)
        idx_rating = header.index(COL_RATING)
        idx_body = header.index(COL_REVIEW_BODY)
        idx_draft = header.index(COL_DRAFT_REPLY)
        idx_status = header.index(COL_STATUS)
    except ValueError:
        return []
    out = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) <= max(idx_status, idx_draft, idx_name):
            continue
        status = (row[idx_status] or "").strip()
        if status not in (STATUS_DRAFT, STATUS_TO_POST):
            continue
        out.append({
            "row": i,
            "review_date": row[idx_date] if len(row) > idx_date else "",
            "review_name": (row[idx_name] or "").strip(),
            "reviewer": row[idx_reviewer] if len(row) > idx_reviewer else "",
            "rating": row[idx_rating] if len(row) > idx_rating else "",
            "body": row[idx_body] if len(row) > idx_body else "",
            "draft": row[idx_draft] if len(row) > idx_draft else "",
            "status": status,
        })
    return out


def update_review_date(row_index_1based: int, review_date: str) -> None:
    """指定行のレビュー日時を更新する。"""
    if not SPREADSHEET_ID:
        return
    header = get_all_rows()[0]
    col_date_idx = header.index(COL_REVIEW_DATE)
    date_col = _column_letter(col_date_idx)
    cell = f"'{SHEET_NAME}'!{date_col}{row_index_1based}"
    _get_sheets_service().spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=cell,
        valueInputOption="USER_ENTERED",
        body={"values": [[review_date]]},
    ).execute()


def get_recent_posted_replies(limit: int = 5) -> list[dict]:
    """最近 N 件の「投稿済み」行を返す。Few-shot 例として AI に渡す用。

    返り値: [{"review_body", "reply", "rating"}, ...]（古い順 → 新しい順）
    """
    rows = get_all_rows()
    if not rows:
        return []
    header = rows[0]
    try:
        idx_status = header.index(COL_STATUS)
        idx_body = header.index(COL_REVIEW_BODY)
        idx_draft = header.index(COL_DRAFT_REPLY)
        idx_rating = header.index(COL_RATING)
    except ValueError:
        return []

    posted = []
    for row in rows[1:]:
        if len(row) <= max(idx_status, idx_draft, idx_body, idx_rating):
            continue
        if (row[idx_status] or "").strip() != STATUS_POSTED:
            continue
        body = (row[idx_body] or "").strip()
        reply = (row[idx_draft] or "").strip()
        if body and reply:
            posted.append({
                "review_body": body,
                "reply": reply,
                "rating": (row[idx_rating] or "").strip(),
            })
    return posted[-limit:]


def get_existing_review_names() -> set[str]:
    """すでにシートに存在するレビュー名のセットを返す。"""
    rows = get_all_rows()
    if not rows:
        return set()
    header = rows[0]
    try:
        idx = header.index(COL_REVIEW_NAME)
    except ValueError:
        return set()
    names = set()
    for row in rows[1:]:
        if len(row) > idx and row[idx]:
            names.add((row[idx] or "").strip())
    return names
