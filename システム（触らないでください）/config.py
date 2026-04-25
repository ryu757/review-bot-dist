"""設定: 環境変数とスプレッドシートから読み込み（配布版・日本語専用）"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# スプレッドシート
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
SHEET_NAME = os.getenv("SHEET_NAME", "レビュー返信")
CONFIG_SHEET_NAME = os.getenv("CONFIG_SHEET_NAME", "設定")

# Anthropic（draft_generator が anthropic.Anthropic() で参照）
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# レビュー返信シートの列定義（翻訳列なし・日本語専用）
COL_REVIEW_DATE = "レビュー日時"
COL_REVIEW_NAME = "レビュー名"
COL_REVIEWER = "レビュアー"
COL_RATING = "評価"
COL_REVIEW_BODY = "レビュー本文"
COL_DRAFT_REPLY = "返信下書き"
COL_STATUS = "ステータス"
COL_UPDATED = "更新日時"

SHEET_HEADERS = [
    COL_REVIEW_DATE,
    COL_REVIEW_NAME,
    COL_REVIEWER,
    COL_RATING,
    COL_REVIEW_BODY,
    COL_DRAFT_REPLY,
    COL_STATUS,
    COL_UPDATED,
]

# 設定シートの構造
CONFIG_HEADERS = ["項目", "値"]
CONFIG_KEY_BUSINESS_NAME = "企業名"
CONFIG_KEY_INDUSTRY = "業界"
CONFIG_KEY_REGION = "地域"
CONFIG_KEY_WEBSITE_URL = "ホームページURL"
CONFIG_KEY_PRIORITY_KEYWORDS = "重点キーワード"
CONFIG_KEY_ANTHROPIC_KEY = "Anthropic APIキー"

DEFAULT_CONFIG_ROWS = [
    [CONFIG_KEY_BUSINESS_NAME, ""],
    [CONFIG_KEY_INDUSTRY, ""],
    [CONFIG_KEY_REGION, ""],            # 例: 横浜市鶴見区
    [CONFIG_KEY_WEBSITE_URL, ""],
    [CONFIG_KEY_PRIORITY_KEYWORDS, ""], # 例: 車検 / 板金 / 輸入車対応（カンマ or スラッシュ区切り）
    [CONFIG_KEY_ANTHROPIC_KEY, ""],
]

# 設定シートで必須の項目（セットアップ完了判定に使用）
REQUIRED_CONFIG_KEYS = [
    CONFIG_KEY_BUSINESS_NAME,
    CONFIG_KEY_INDUSTRY,
    CONFIG_KEY_ANTHROPIC_KEY,
]

# ステータス値
STATUS_DRAFT = "下書き"
STATUS_TO_POST = "投稿する"
STATUS_POSTED = "投稿済み"
