"""
Playwright でブラウザ操作して Google ビジネスプロフィールの
レビュー取得・返信投稿を行うクライアント。
"""
from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright, Page

import re
from datetime import datetime, timedelta

SESSION_DIR = Path(__file__).parent / "google_session"
STATE_FILE = SESSION_DIR / "state.json"
BUSINESS_URL = "https://business.google.com"

# 環境変数で headless モードを切り替え（デフォルト: headless）
import os
HEADLESS = os.getenv("BROWSER_HEADLESS", "1") == "1"

# 通知モジュール（任意）
try:
    import notify as _notify  # type: ignore
except ImportError:
    _notify = None  # type: ignore

# レビューカードを検出するセレクタ候補（上から順に試す）
REVIEW_CARD_SELECTORS = [
    "[data-review-id]",
    "[jscontroller][data-review-id]",
    "div[role='listitem'][data-review-id]",
]

# 「次へ」ボタンのセレクタ候補
NEXT_BUTTON_SELECTORS = [
    'button[aria-label="次へ"]',
    'button[aria-label="Next"]',
    'button[aria-label="次のページ"]',
    'button[jsname][aria-label*="次"]',
]

# 「返信」ボタンのテキスト候補（厳密一致）
REPLY_BUTTON_TEXTS = ["返信", "Reply"]

# 送信ボタンのテキスト候補
SUBMIT_BUTTON_TEXTS = ["返信を投稿", "送信", "Submit", "Post reply", "Post", "投稿"]


def _parse_relative_date(text: str) -> str:
    """「3 日前」「2 週間前」などの相対日時を YYYY-MM-DD に変換。"""
    from dateutil.relativedelta import relativedelta

    now = datetime.now()
    text = text.strip()
    if not text:
        return now.strftime("%Y-%m-%d")

    # 「○ 分前」
    m = re.search(r'(\d+)\s*分前', text)
    if m:
        return (now - timedelta(minutes=int(m.group(1)))).strftime("%Y-%m-%d")

    # 「○ 時間前」
    m = re.search(r'(\d+)\s*時間前', text)
    if m:
        return (now - timedelta(hours=int(m.group(1)))).strftime("%Y-%m-%d")

    # 「○ 日前」
    m = re.search(r'(\d+)\s*日前', text)
    if m:
        return (now - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")

    # 「○ 週間前」
    m = re.search(r'(\d+)\s*週間前', text)
    if m:
        return (now - timedelta(weeks=int(m.group(1)))).strftime("%Y-%m-%d")

    # 「○ か月前」「○ ヶ月前」「○ カ月前」
    m = re.search(r'(\d+)\s*[かヶカ]月前', text)
    if m:
        return (now - relativedelta(months=int(m.group(1)))).strftime("%Y-%m-%d")

    # 「○ 年前」
    m = re.search(r'(\d+)\s*年前', text)
    if m:
        return (now - relativedelta(years=int(m.group(1)))).strftime("%Y-%m-%d")

    # English: "X minutes/hours/days/weeks/months/years ago"
    m = re.search(r'(\d+)\s*minute', text, re.IGNORECASE)
    if m:
        return (now - timedelta(minutes=int(m.group(1)))).strftime("%Y-%m-%d")
    m = re.search(r'(\d+)\s*hour', text, re.IGNORECASE)
    if m:
        return (now - timedelta(hours=int(m.group(1)))).strftime("%Y-%m-%d")
    m = re.search(r'(\d+)\s*day', text, re.IGNORECASE)
    if m:
        return (now - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")
    m = re.search(r'(\d+)\s*week', text, re.IGNORECASE)
    if m:
        return (now - timedelta(weeks=int(m.group(1)))).strftime("%Y-%m-%d")
    m = re.search(r'(\d+)\s*month', text, re.IGNORECASE)
    if m:
        return (now - relativedelta(months=int(m.group(1)))).strftime("%Y-%m-%d")
    m = re.search(r'(\d+)\s*year', text, re.IGNORECASE)
    if m:
        return (now - relativedelta(years=int(m.group(1)))).strftime("%Y-%m-%d")

    # "a day ago", "a week ago" etc. (数字なし)
    if re.search(r'a\s+day', text, re.IGNORECASE):
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    if re.search(r'a\s+week', text, re.IGNORECASE):
        return (now - timedelta(weeks=1)).strftime("%Y-%m-%d")
    if re.search(r'a\s+month', text, re.IGNORECASE):
        return (now - relativedelta(months=1)).strftime("%Y-%m-%d")
    if re.search(r'a\s+year', text, re.IGNORECASE):
        return (now - relativedelta(years=1)).strftime("%Y-%m-%d")

    return text


def _random_wait(page: Page, low: float = 1.0, high: float = 3.0) -> None:
    page.wait_for_timeout(int(random.uniform(low, high) * 1000))


def _open_browser(playwright, headless: bool = False):
    """ブラウザとコンテキストを開く。ログイン済みセッションを復元する。"""
    browser = playwright.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        locale="ja-JP",
        timezone_id="Asia/Tokyo",
        storage_state=str(STATE_FILE) if STATE_FILE.exists() else None,
    )
    page = context.new_page()
    return browser, context, page


def _save_and_close(context, browser):
    """セッションを保存してブラウザを閉じる。"""
    try:
        SESSION_DIR.mkdir(exist_ok=True)
        context.storage_state(path=str(STATE_FILE))
    except Exception as e:
        print(f"  セッション保存に失敗: {e}")
    try:
        context.close()
    except Exception:
        pass
    try:
        browser.close()
    except Exception:
        pass


def login_interactive() -> None:
    """
    初回ログイン用: ブラウザを開いて手動でログインしてもらう。
    5分間ブラウザを開いたままにし、その間にログインしてもらう。
    """
    SESSION_DIR.mkdir(exist_ok=True)
    p = sync_playwright().start()
    browser, context, page = _open_browser(p, headless=HEADLESS)
    page.goto(BUSINESS_URL)
    print("=" * 50)
    print("ブラウザが開きました。")
    print("Google アカウントでログインしてください。")
    print("5分後に自動でブラウザが閉じます。")
    print("=" * 50)
    time.sleep(300)
    _save_and_close(context, browser)
    p.stop()
    print("セッションを保存しました。")


def _extract_timestamps_from_html(html: str) -> dict[str, str]:
    """
    HTMLに埋め込まれたJSデータからレビューの正確なタイムスタンプを抽出する。
    返り値: {レビュアー名: "YYYY-MM-DD"} のマッピング。
    """
    timestamp_map: dict[str, str] = {}

    # JSデータ内のレビュー配列: ["reviewId",null,...,TIMESTAMP,...,["contribId","Name",...]]
    pattern = (
        r'\["Ci9[A-Za-z0-9+/=]+",null,null,null,null,'
        r'"[^"]*","[^"]*",null,(\d{13})'
        r'.*?\["(\d+)","([^"]+)","https://www\.google\.com/maps/contrib/'
    )
    for m in re.finditer(pattern, html, re.DOTALL):
        ts_ms = int(m.group(1))
        reviewer_name = m.group(3)
        dt = datetime.fromtimestamp(ts_ms / 1000)
        timestamp_map[reviewer_name] = dt.strftime("%Y-%m-%d")

    return timestamp_map


def _extract_timestamps_from_response(body: str, timestamp_map: dict[str, str]) -> None:
    """
    Google batchexecute のレスポンス本文からレビュータイムスタンプを抽出して
    timestamp_map に追加する。
    """
    # batchexecute レスポンスはネストされたJSON文字列（エスケープ済み）を含む
    # まずエスケープを解除したバージョンでもパースを試みる
    texts = [body]
    # \" → " のエスケープ解除
    if '\\"' in body:
        texts.append(body.replace('\\"', '"').replace('\\\\', '\\').replace('\\n', '\n').replace('\\u003d', '=').replace('\\u0026', '&'))

    pattern = (
        r'\["Ci9[A-Za-z0-9+/=]+",null,null,null,null,'
        r'(?:"(?:[^"\\]|\\.)*","(?:[^"\\]|\\.)*"|null,null),null,(\d{13})'
        r'.*?\["(\d+)","([^"]+)","https://www\.google\.com/maps/contrib/'
    )
    for text in texts:
        for m in re.finditer(pattern, text, re.DOTALL):
            ts_ms = int(m.group(1))
            reviewer_name = m.group(3)
            dt = datetime.fromtimestamp(ts_ms / 1000)
            if reviewer_name not in timestamp_map:
                timestamp_map[reviewer_name] = dt.strftime("%Y-%m-%d")


def _find_review_cards(page: Page) -> list:
    """複数のセレクタを試してレビューカードを取得する（フォールバック付き）。"""
    for sel in REVIEW_CARD_SELECTORS:
        cards = page.locator(sel).all()
        if cards:
            return cards
    return []


def _click_next_button(page: Page) -> bool:
    """複数のセレクタを試して「次へ」ボタンをクリックする。"""
    for sel in NEXT_BUTTON_SELECTORS:
        btn = page.locator(sel)
        if btn.count() and btn.is_enabled():
            btn.click()
            return True
    return False


def _parse_review_cards(page: Page, timestamp_map: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """現在のページに表示されているレビューカードをパースする。"""
    if timestamp_map is None:
        timestamp_map = {}

    reviews = []
    cards = _find_review_cards(page)
    for card in cards:
        try:
            review_id = card.get_attribute("data-review-id") or ""
            parent = card.locator("..")

            reviewer = parent.evaluate(
                '''el => {
                    const a = el.querySelector("a[href*='maps/contrib']");
                    return a ? a.textContent.trim() : "";
                }'''
            )

            # 正確なタイムスタンプを優先使用、なければ相対日時からの推定にフォールバック
            review_date = timestamp_map.get(reviewer, "")
            if not review_date:
                # ホバーでツールチップから正確な日時を取得試行
                review_date_raw = parent.evaluate(
                    '''el => {
                        // NhZJzb はレビュー日時のspan
                        const dateSpan = el.querySelector("span.zWmYWd.NhZJzb");
                        if (dateSpan) {
                            // title/aria-label属性に正確な日時がある場合
                            const title = dateSpan.getAttribute("title") || dateSpan.getAttribute("aria-label") || "";
                            if (title) return "EXACT:" + title;
                            return dateSpan.textContent.trim();
                        }
                        const reviewerSection = el.querySelector(".k4kupc");
                        if (reviewerSection) {
                            const spans = reviewerSection.querySelectorAll("span");
                            for (const span of spans) {
                                const text = span.textContent.trim();
                                if (text.match(/前$/) || text.match(/ago$/i)) {
                                    const title = span.getAttribute("title") || span.getAttribute("aria-label") || "";
                                    if (title) return "EXACT:" + title;
                                    return text;
                                }
                            }
                        }
                        return "";
                    }'''
                )
                if review_date_raw.startswith("EXACT:"):
                    review_date = review_date_raw[6:]
                else:
                    review_date = _parse_relative_date(review_date_raw)

            filled_stars = parent.evaluate(
                '''el => el.querySelectorAll("span.DPvwYc.MOLvNc").length'''
            )
            rating = str(filled_stars) if filled_stars > 0 else "5"

            body = parent.evaluate(
                '''el => {
                    const orig = el.querySelector("[jsname='QUIPvd']");
                    if (orig && orig.textContent.trim()) {
                        let text = orig.textContent.trim();
                        if (text.includes("（原文）")) {
                            text = text.split("（原文）").pop().trim();
                        } else if (text.includes("(Original)")) {
                            text = text.split("(Original)").pop().trim();
                        }
                        text = text.replace("（Google による翻訳）", "").trim();
                        text = text.replace("(Translated by Google)", "").trim();
                        if (text) return text;
                    }
                    const trans = el.querySelector("[jsname='an9Zef']");
                    if (trans) {
                        let text = trans.textContent.trim();
                        text = text.replace("（Google による翻訳）", "").trim();
                        text = text.replace("(Translated by Google)", "").trim();
                        text = text.replace(/その他$/, "").trim();
                        text = text.replace(/\\.\\.\\.\\s*$/, "").trim();
                        return text;
                    }
                    return "";
                }'''
            )

            has_reply_btn = parent.evaluate(
                '''el => {
                    const btns = el.querySelectorAll("button");
                    return Array.from(btns).some(b => b.textContent.includes("返信"));
                }'''
            )
            has_reply = not has_reply_btn

            reviews.append({
                "review_id": review_id,
                "reviewer": reviewer or "（匿名）",
                "rating": rating,
                "body": body,
                "review_date": review_date,
                "has_reply": has_reply,
            })
        except Exception as e:
            print(f"  レビューの解析中にエラー: {e}")
            continue
    return reviews


def fetch_reviews() -> list[dict[str, Any]]:
    """
    Google ビジネスプロフィールからレビュー一覧を取得。
    ページネーションで全ページを巡回する。
    返り値: [{"reviewer", "rating", "body", "review_id", "has_reply"}, ...]
    """
    reviews = []
    seen_ids: set[str] = set()
    timestamp_map: dict[str, str] = {}
    p = sync_playwright().start()
    browser, context, page = _open_browser(p, headless=HEADLESS)

    try:
        # ネットワークレスポンスを傍受してタイムスタンプを収集
        def _on_response(response):
            try:
                ct = response.headers.get("content-type", "")
                if ("text" in ct or "json" in ct or "javascript" in ct) and response.status == 200:
                    body = response.text()
                    _extract_timestamps_from_response(body, timestamp_map)
            except Exception:
                pass

        page.on("response", _on_response)

        # ビジネスプロフィールのレビューページへ
        page.goto(f"{BUSINESS_URL}/reviews", wait_until="domcontentloaded", timeout=60000)
        _random_wait(page, 3, 5)

        # ログインが必要か確認
        if "accounts.google.com" in page.url:
            print("ログインが必要です。先に `python main.py login` を実行してください。")
            return []

        # レビューの読み込みを待つ
        page.wait_for_timeout(5000)

        # 初回ページのHTMLからタイムスタンプを抽出
        initial_html = page.content()
        _extract_timestamps_from_response(initial_html, timestamp_map)
        print(f"  タイムスタンプ取得: {len(timestamp_map)} 件")

        # デバッグ: 現在のURLとページタイトルを表示
        print(f"  URL: {page.url}")
        print(f"  タイトル: {page.title()}")

        # スクリーンショットを保存（デバッグ用）
        page.screenshot(path="debug_reviews.png")
        print("  スクリーンショットを debug_reviews.png に保存しました。")

        # ページネーションで全ページを巡回
        page_num = 1
        MAX_PAGES = 20  # 安全上限

        while page_num <= MAX_PAGES:
            # 現在のページのレビューをパース
            page_reviews = _parse_review_cards(page, timestamp_map)
            print(f"  ページ {page_num}: {len(page_reviews)} 件のレビュー")

            new_count = 0
            for r in page_reviews:
                if r["review_id"] not in seen_ids:
                    seen_ids.add(r["review_id"])
                    reviews.append(r)
                    new_count += 1

            if new_count == 0 and page_num > 1:
                # 新しいレビューが見つからなければ終了
                break

            # 「次へ」ボタンをフォールバック付きでクリック
            if not _click_next_button(page):
                break
            page.wait_for_timeout(3000)
            _random_wait(page, 1, 2)
            page_num += 1

        # デバッグ用にHTMLを保存
        html = page.content()
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("  debug_page.html を保存しました。")

    finally:
        _save_and_close(context, browser)
        p.stop()

    return reviews


def post_reply(review_id: str, reply_text: str) -> bool:
    """
    指定レビューに返信を投稿する。
    成功時 True、失敗時 False を返す。
    """
    p = sync_playwright().start()
    browser, context, page = _open_browser(p, headless=HEADLESS)

    try:
        page.goto(f"{BUSINESS_URL}/reviews", wait_until="domcontentloaded", timeout=60000)
        _random_wait(page, 3, 5)

        if "accounts.google.com" in page.url:
            print("ログインが必要です。")
            return False

        page.wait_for_timeout(5000)

        # ページネーションで対象レビューを探す
        target = None
        for _ in range(20):
            t = page.locator(f'[data-review-id="{review_id}"]')
            if t.count():
                target = t
                break
            if not _click_next_button(page):
                break
            page.wait_for_timeout(3000)
            _random_wait(page, 1, 2)

        if target is None:
            print(f"レビューが見つかりません: {review_id}")
            return False

        # 親要素を取得（返信ボタンは親にある）
        parent = target.locator("..")

        # 二重投稿防止チェックは撤去（誤検知で投稿が走らない問題があったため）。
        # 万一の重複は人間が Google マップ側で削除する運用とする。

        parent.scroll_into_view_if_needed()
        _random_wait(page)

        # 「返信」ボタンをクリック（JS で親要素から探す）
        clicked = parent.evaluate(
            '''el => {
                const btns = el.querySelectorAll("button");
                for (const btn of btns) {
                    if (btn.textContent.includes("返信") || btn.textContent.includes("Reply")) {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }'''
        )
        if not clicked:
            print(f"返信ボタンが見つかりません: {review_id}")
            return False

        _random_wait(page, 2, 3)

        # テキストエリアに入力
        textarea = page.locator("textarea").last
        if not textarea.count():
            print("返信入力欄が見つかりません。")
            return False

        textarea.fill(reply_text)
        _random_wait(page, 0.5, 1.5)

        # 送信ボタンをクリック（ページ全体から探す）
        submitted = page.evaluate(
            '''() => {
                const btns = document.querySelectorAll("button");
                for (const btn of btns) {
                    const text = btn.textContent.trim();
                    if (text === "返信を投稿" || text === "送信" || text === "Submit" || text === "Post reply") {
                        btn.click();
                        return true;
                    }
                }
                return false;
            }'''
        )

        if not submitted:
            print("送信ボタンが見つかりません。")
            return False

        _random_wait(page, 3, 5)
        return True
    finally:
        _save_and_close(context, browser)
        p.stop()
