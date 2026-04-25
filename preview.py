"""シートの「下書き」全行を、新SEO プロンプトで再生成して表示するだけのスクリプト。
シートは一切変更しない。「.venv/bin/python preview.py」をシステムフォルダ内で実行。
"""
import sys
sys.path.insert(0, '.')
from config import (
    CONFIG_KEY_BUSINESS_NAME, CONFIG_KEY_INDUSTRY, CONFIG_KEY_REGION,
    CONFIG_KEY_WEBSITE_URL, CONFIG_KEY_PRIORITY_KEYWORDS,
    COL_STATUS, COL_REVIEWER, COL_RATING, COL_REVIEW_BODY, COL_DRAFT_REPLY,
    STATUS_DRAFT,
)
from sheets_client import get_all_rows, get_business_config, get_recent_posted_replies
from seo_keywords import extract_seo_keywords
from draft_generator import generate_draft


def main():
    cfg = get_business_config()
    print("SEO 関連語を取得中...")
    seo = extract_seo_keywords(
        cfg.get(CONFIG_KEY_BUSINESS_NAME, ''),
        cfg.get(CONFIG_KEY_INDUSTRY, ''),
        cfg.get(CONFIG_KEY_REGION, ''),
    )
    if seo:
        print(f"  SEO: {', '.join(seo[:8])}")
    past = get_recent_posted_replies(limit=5)
    if past:
        print(f"  過去返信例 {len(past)} 件をトーン参考に使用")

    rows = get_all_rows()
    if not rows:
        print("シートが空です")
        return
    header = rows[0]
    i_status = header.index(COL_STATUS)
    i_reviewer = header.index(COL_REVIEWER)
    i_rating = header.index(COL_RATING)
    i_body = header.index(COL_REVIEW_BODY)
    i_draft = header.index(COL_DRAFT_REPLY)

    for n, row in enumerate(rows[1:], start=2):
        if len(row) <= max(i_status, i_draft, i_body):
            continue
        if (row[i_status] or '').strip() != STATUS_DRAFT:
            continue
        reviewer = row[i_reviewer] if len(row) > i_reviewer else ''
        rating = row[i_rating] if len(row) > i_rating else '0'
        body = row[i_body] if len(row) > i_body else ''
        print(f"\n=== 行{n}: {reviewer} ★{rating} ===")
        print(f"レビュー: {body[:200]}")
        print(f"--- 旧下書き ---")
        print(f"{(row[i_draft] or '')[:400]}")
        print(f"--- 新下書き(SEO 考慮) ---")
        new_draft = generate_draft(
            reviewer, rating, body,
            cfg.get(CONFIG_KEY_BUSINESS_NAME, ''),
            cfg.get(CONFIG_KEY_INDUSTRY, ''),
            cfg.get(CONFIG_KEY_WEBSITE_URL, ''),
            region=cfg.get(CONFIG_KEY_REGION, ''),
            priority_keywords=cfg.get(CONFIG_KEY_PRIORITY_KEYWORDS, ''),
            seo_suggestions=seo,
            past_replies=past,
        )
        print(new_draft)


if __name__ == "__main__":
    main()
