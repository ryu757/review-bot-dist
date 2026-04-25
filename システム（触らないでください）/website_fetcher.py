"""ホームページの内容を取得・キャッシュするモジュール（配布版）

24時間 TTL のキャッシュを credentials/website_cache.json に保存する。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

CACHE_FILE = Path(__file__).parent / "credentials" / "website_cache.json"
CACHE_TTL_HOURS = 24
MAX_CONTENT_CHARS = 5000


def fetch_website_text(url: str, force: bool = False) -> str:
    """指定 URL からテキストを抽出して返す。キャッシュ有効期限内ならキャッシュを使う。

    取得に失敗した場合は空文字列を返す（呼び出し元で「未取得」として扱う）。
    """
    if not url:
        return ""

    if not force and CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text())
            if cache.get("url") == url:
                fetched = datetime.fromisoformat(cache.get("fetched_at", ""))
                if datetime.now() - fetched < timedelta(hours=CACHE_TTL_HOURS):
                    return cache.get("content", "")
        except Exception:
            pass

    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "ja,en;q=0.5",
            },
            timeout=15,
        )
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or resp.encoding

        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.decompose()

        title = (soup.title.string or "").strip() if soup.title else ""
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag:
            meta_desc = (meta_tag.get("content") or "").strip()

        body_text = soup.get_text(separator=" ", strip=True)
        body_text = re.sub(r"\s+", " ", body_text)

        content = (
            f"【ページタイトル】{title}\n"
            f"【メタ説明】{meta_desc}\n"
            f"【本文抜粋】{body_text[:MAX_CONTENT_CHARS]}"
        )

        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps(
                {
                    "url": url,
                    "fetched_at": datetime.now().isoformat(),
                    "content": content,
                },
                ensure_ascii=False,
            )
        )
        return content

    except Exception as e:
        print(f"  ホームページ取得失敗 ({url}): {e}")
        # キャッシュが古くてもあれば使う
        if CACHE_FILE.exists():
            try:
                cache = json.loads(CACHE_FILE.read_text())
                if cache.get("url") == url:
                    return cache.get("content", "")
            except Exception:
                pass
        return ""
