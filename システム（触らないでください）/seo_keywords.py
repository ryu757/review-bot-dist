"""SEO キーワード取得モジュール（Google Suggest API 連携）

Google が公開している無料・認証不要のサジェストエンドポイントから、
実際にユーザーが検索しているキーワードを取得して返信プロンプトに渡す。

24 時間キャッシュ（credentials/seo_cache.json）で API 呼び出しを抑制。
"""
from __future__ import annotations

import json
import re
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

CACHE_FILE = Path(__file__).parent / "credentials" / "seo_cache.json"
CACHE_TTL_HOURS = 24


def _load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text())
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False))
    except Exception:
        pass


def _fetch_suggestions(query: str) -> list[str]:
    """Google Suggest API（Firefox 互換 JSON 形式）から候補取得。"""
    encoded = urllib.parse.quote(query)
    url = (
        f"https://suggestqueries.google.com/complete/search"
        f"?client=firefox&hl=ja&q={encoded}"
    )
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # 形式: ["query", ["suggestion1", "suggestion2", ...]]
        if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
            return [s for s in data[1] if isinstance(s, str)]
    except Exception:
        pass
    return []


def get_suggestions_cached(query: str) -> list[str]:
    """1 クエリ分のサジェストを取得（キャッシュ優先）。"""
    if not query:
        return []
    cache = _load_cache()
    entry = cache.get(query)
    if entry:
        try:
            fetched = datetime.fromisoformat(entry.get("fetched_at", ""))
            if datetime.now() - fetched < timedelta(hours=CACHE_TTL_HOURS):
                return entry.get("suggestions", [])
        except Exception:
            pass

    suggestions = _fetch_suggestions(query)
    cache[query] = {
        "fetched_at": datetime.now().isoformat(),
        "suggestions": suggestions,
    }
    _save_cache(cache)
    return suggestions


def extract_seo_keywords(
    business_name: str,
    industry: str,
    region: str = "",
    max_keywords: int = 12,
) -> list[str]:
    """事業情報から SEO キーワード候補を抽出。

    複数のクエリでサジェストを取り、よく出てくる単語を抽出して返す。
    """
    queries: list[str] = []
    if industry and region:
        queries.append(f"{industry} {region}")
    if industry:
        queries.append(industry)
    if business_name and region:
        queries.append(f"{business_name} {region}")
    if business_name:
        queries.append(business_name)

    word_count: dict[str, int] = {}
    base_terms = {
        (industry or "").strip(),
        (region or "").strip(),
        (business_name or "").strip(),
    }
    base_terms.discard("")

    for q in queries:
        for sug in get_suggestions_cached(q):
            # クエリそのものを除いた残りの語を抽出
            tail = sug
            for term in base_terms:
                tail = tail.replace(term, " ")
            # 空白／記号で分割
            words = [w for w in re.split(r"[\s、,.\-/]+", tail) if w]
            for w in words:
                # 1 文字や数字のみは除外
                if len(w) < 2 or w.isdigit():
                    continue
                word_count[w] = word_count.get(w, 0) + 1

    # 頻度順に並べて返す
    sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:max_keywords]]
