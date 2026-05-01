"""新着レビューを取得しスプレッドシートに下書きを追加（配布版・日本語専用）"""
from __future__ import annotations

from datetime import datetime

from config import (
    STATUS_DRAFT,
    CONFIG_KEY_BUSINESS_NAME,
    CONFIG_KEY_INDUSTRY,
    CONFIG_KEY_REGION,
    CONFIG_KEY_WEBSITE_URL,
    CONFIG_KEY_PRIORITY_KEYWORDS,
    CONFIG_KEY_CLOSING_PHRASE,
    COL_REVIEW_DATE,
    COL_REVIEWER,
    COL_RATING,
    COL_REVIEW_BODY,
    COL_DRAFT_REPLY,
    COL_STATUS,
)
from draft_generator import generate_draft
from browser_client import fetch_reviews
from sheets_client import (
    ensure_sheet_ready,
    append_draft_row,
    get_existing_review_names,
    get_business_config,
    get_recent_posted_replies,
    get_all_rows,
    update_review_date,
    update_draft_cell,
)
from seo_keywords import extract_seo_keywords


def sync_new_reviews_to_sheet() -> int:
    """新着レビューのうち未登録かつ未返信を、下書き付きでシートに追加する。"""
    ensure_sheet_ready()
    existing = get_existing_review_names()

    print("ブラウザでレビューを取得中...")
    all_reviews = fetch_reviews()
    print(f"  {len(all_reviews)} 件のレビューを取得しました。")

    if not all_reviews:
        print("⚠ レビューを取得できませんでした。セッション切れの可能性があります。")
        print("  `python main.py login` で再ログインしてください。")
        return 0

    config = get_business_config()
    business_name = config.get(CONFIG_KEY_BUSINESS_NAME, "")
    industry = config.get(CONFIG_KEY_INDUSTRY, "")
    region = config.get(CONFIG_KEY_REGION, "")
    website_url = config.get(CONFIG_KEY_WEBSITE_URL, "")
    priority_keywords = config.get(CONFIG_KEY_PRIORITY_KEYWORDS, "")
    closing_phrase = config.get(CONFIG_KEY_CLOSING_PHRASE, "")

    if not business_name or not industry:
        print("⚠ スプレッドシートの「設定」シートに 企業名 / 業界 を記入してください。")
        print("  記入が無いと一般的な返信文しか生成できません。")

    # SEO サジェスト取得（1 回・キャッシュ有り）と過去返信例（Few-shot）を sync 全体で使い回す
    print("  SEO 関連語を取得中（Google サジェスト・キャッシュ24h）...")
    seo_suggestions = extract_seo_keywords(business_name, industry, region)
    if seo_suggestions:
        print(f"    取得語: {', '.join(seo_suggestions[:8])}")
    past_replies = get_recent_posted_replies(limit=5)
    if past_replies:
        print(f"  過去の投稿済み返信 {len(past_replies)} 件をトーン参考として使用")

    added = 0
    skipped_existing = 0
    skipped_replied = 0
    for review in all_reviews:
        review_id = review.get("review_id") or ""
        print(f"  - {review.get('reviewer')} | ★{review.get('rating')} | 返信済み={review.get('has_reply')} | ID={review_id[:20]}...")
        if not review_id or review_id in existing:
            skipped_existing += 1
            continue
        if review.get("has_reply"):
            skipped_replied += 1
            continue

        reviewer = review.get("reviewer") or "（匿名）"
        rating = review.get("rating") or "0"
        body = review.get("body") or ""

        print(f"  下書き生成中: {reviewer} (★{rating})...")
        draft = generate_draft(
            reviewer, rating, body, business_name, industry, website_url,
            region=region,
            priority_keywords=priority_keywords,
            seo_suggestions=seo_suggestions,
            past_replies=past_replies,
            closing_phrase=closing_phrase,
        )

        review_date = review.get("review_date") or datetime.now().strftime("%Y-%m-%d %H:%M")
        row = [
            review_date,
            review_id,
            reviewer,
            rating,
            body,
            draft,
            STATUS_DRAFT,
            "",
        ]
        append_draft_row(row)
        existing.add(review_id)
        added += 1

    print(f"  スキップ: 登録済み={skipped_existing}, 返信済み={skipped_replied}")
    return added


def regenerate_drafts() -> tuple[int, int]:
    """ステータス=「下書き」の全行に対し、現行ロジックで返信下書きを再生成する。

    用途: 設定シートの値変更（固定文末・重点キーワード等）や、
          システム側のプロンプト改良を、既存の未投稿下書きに適用したいとき。
    返り値: (再生成成功数, 失敗数)
    注意: 投稿済み・投稿予定（投稿する）の行は対象外。
          人間が編集した下書きも上書きされるので運用時は要確認。
    """
    ensure_sheet_ready()
    rows = get_all_rows()
    if not rows:
        print("シートにデータがありません。")
        return 0, 0

    header = rows[0]
    try:
        idx_status = header.index(COL_STATUS)
        idx_reviewer = header.index(COL_REVIEWER)
        idx_rating = header.index(COL_RATING)
        idx_body = header.index(COL_REVIEW_BODY)
        idx_draft = header.index(COL_DRAFT_REPLY)
    except ValueError as e:
        print(f"ヘッダーが不正です: {e}")
        return 0, 0

    config = get_business_config()
    business_name = config.get(CONFIG_KEY_BUSINESS_NAME, "")
    industry = config.get(CONFIG_KEY_INDUSTRY, "")
    region = config.get(CONFIG_KEY_REGION, "")
    website_url = config.get(CONFIG_KEY_WEBSITE_URL, "")
    priority_keywords = config.get(CONFIG_KEY_PRIORITY_KEYWORDS, "")
    closing_phrase = config.get(CONFIG_KEY_CLOSING_PHRASE, "")

    if not business_name or not industry:
        print("⚠ 設定シートの 企業名 / 業界 が未入力です。")
        print("  記入が無いと一般的な返信文しか生成できません。")

    # 再生成対象（ステータス=下書き）を抽出
    targets = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) <= max(idx_status, idx_draft, idx_body, idx_reviewer, idx_rating):
            continue
        if (row[idx_status] or "").strip() != STATUS_DRAFT:
            continue
        targets.append({
            "row_index": i,
            "reviewer": (row[idx_reviewer] or "").strip(),
            "rating": (row[idx_rating] or "").strip(),
            "body": (row[idx_body] or "").strip(),
        })

    if not targets:
        print("再生成対象の下書きはありません。")
        return 0, 0

    print(f"再生成対象: {len(targets)} 件")
    print("  SEO 関連語を取得中（Google サジェスト・キャッシュ24h）...")
    seo_suggestions = extract_seo_keywords(business_name, industry, region)
    if seo_suggestions:
        print(f"    取得語: {', '.join(seo_suggestions[:8])}")
    past_replies = get_recent_posted_replies(limit=5)
    if past_replies:
        print(f"  過去の投稿済み返信 {len(past_replies)} 件をトーン参考として使用")

    ok = 0
    ng = 0
    for t in targets:
        print(f"  - 行{t['row_index']}: {t['reviewer'] or '(匿名)'} (★{t['rating']}) 再生成中...")
        try:
            new_draft = generate_draft(
                t["reviewer"] or "（匿名）",
                t["rating"] or "0",
                t["body"],
                business_name, industry, website_url,
                region=region,
                priority_keywords=priority_keywords,
                seo_suggestions=seo_suggestions,
                past_replies=past_replies,
                closing_phrase=closing_phrase,
            )
            update_draft_cell(t["row_index"], new_draft)
            ok += 1
        except Exception as e:
            print(f"    エラー: {e}")
            ng += 1

    return ok, ng


def fix_review_dates() -> int:
    """既存行のレビュー日時を、ブラウザから取得した正確なタイムスタンプで修正する。"""
    ensure_sheet_ready()
    rows = get_all_rows()
    if not rows:
        print("シートにデータがありません。")
        return 0

    header = rows[0]
    try:
        idx_date = header.index(COL_REVIEW_DATE)
        idx_reviewer = header.index(COL_REVIEWER)
    except ValueError as e:
        print(f"ヘッダーが不正です: {e}")
        return 0

    print("ブラウザでレビューを取得中...")
    all_reviews = fetch_reviews()
    print(f"  {len(all_reviews)} 件のレビューを取得しました。")

    if not all_reviews:
        return 0

    date_map: dict[str, str] = {}
    for review in all_reviews:
        reviewer = review.get("reviewer") or ""
        review_date = review.get("review_date") or ""
        if reviewer and review_date:
            date_map[reviewer] = review_date

    updated = 0
    for i, row in enumerate(rows[1:], start=2):
        if len(row) <= max(idx_date, idx_reviewer):
            continue
        reviewer = (row[idx_reviewer] or "").strip()
        current_date = (row[idx_date] or "").strip()
        correct_date = date_map.get(reviewer, "")
        if correct_date and correct_date != current_date:
            print(f"  行{i}: {reviewer} の日付を修正: {current_date} → {correct_date}")
            update_review_date(i, correct_date)
            updated += 1
    return updated
