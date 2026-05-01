"""レビュー返信下書き生成（配布版・日本語専用・SEO最適化・Few-shot学習）"""
from __future__ import annotations

import os

import anthropic

from website_fetcher import fetch_website_text


def generate_draft(
    reviewer: str,
    rating: str,
    review_body: str,
    business_name: str,
    industry: str,
    website_url: str,
    region: str = "",
    priority_keywords: str = "",
    seo_suggestions: list[str] | None = None,
    past_replies: list[dict] | None = None,
    closing_phrase: str = "",
) -> str:
    """レビューに対する日本語の返信下書きを生成。

    AI に「思考ステップ」を踏ませてから返信を書かせる構造化プロンプト。
    SEO キーワード（サジェスト + クライアント指定）と過去返信例（Few-shot）を活用。
    """
    business_name = business_name or "（企業名未設定）"
    industry = industry or "（業界未設定）"
    seo_suggestions = seo_suggestions or []
    past_replies = past_replies or []

    website_text = fetch_website_text(website_url) if website_url else ""

    # ホームページ情報セクション
    if website_text:
        website_section = (
            "\n## 自社ホームページから抽出した事実情報（これ以外の情報は推測しないこと）\n"
            f"{website_text}\n"
        )
        fabrication_rule = (
            "**情報の捏造を絶対にしない**: 上記ホームページに書かれていない"
            "サービス名・特典・特徴・実績・受賞歴・キャンペーン・スタッフ名・店舗詳細などは"
            "一切使わない。書かれている内容のみ言及する。"
        )
    else:
        website_section = (
            "\n## 自社ホームページの情報: 未取得\n"
            "（具体的なサービス名・特徴には触れないこと）\n"
        )
        fabrication_rule = (
            "**情報の捏造を絶対にしない**: 具体的なサービス名・特典・特徴・実績・キャンペーン等は"
            "一切使わない。一般的な感謝・謝罪の表現にとどめる。"
        )

    # 地域セクション
    region_section = (
        f"\n## 地域: {region}（地域名は1度だけ自然に含めると地域SEOに効く）\n"
        if region else ""
    )

    # SEO セクション
    seo_lines = []
    if priority_keywords:
        seo_lines.append(f"- **重点キーワード（必ず1つは含める）**: {priority_keywords}")
    if seo_suggestions:
        suggested_str = ", ".join(seo_suggestions[:10])
        seo_lines.append(f"- **検索されている関連語（自然に1〜2語選んで含める）**: {suggested_str}")
    seo_section = ""
    if seo_lines:
        seo_section = (
            "\n## SEO キーワード（返信内に自然に溶け込ませる）\n"
            + "\n".join(seo_lines) + "\n"
        )

    # Few-shot セクション
    examples_section = ""
    if past_replies:
        examples_lines = []
        for i, r in enumerate(past_replies, 1):
            body = (r.get("review_body") or "")[:120]
            reply = r.get("reply") or ""
            examples_lines.append(f"### 例{i}\nレビュー: {body}\n返信: {reply}")
        examples_section = (
            "\n## このお店の過去の返信例（トーン・言葉遣いをこれに合わせる）\n"
            + "\n\n".join(examples_lines) + "\n"
        )

    # 固定文末セクション（指定があれば AI には締めを書かせず、後で必ず付加する）
    closing_section = ""
    if closing_phrase:
        closing_section = (
            "\n## 末尾に自動付加される固定文末（重要）\n"
            "あなたが書いた本文の直後に、システムが下記の文章を改行を挟んで**必ずそのまま付加**します:\n"
            "```\n"
            f"{closing_phrase}\n"
            "```\n"
            "そのため、以下を**厳守**してください:\n"
            "- 本文の最後に「またのご来店をお待ちしております」「○○店一同」など、締めの挨拶や署名は**書かない**\n"
            "- 上記固定文末に含まれる**店名・サロン名・スタッフ表記・地域名・呼びかけ**などを、本文の末尾2文以内で**重複させない**\n"
            "  （例: 固定文末に「○○店スタッフより」とあるなら、本文末尾で「○○店一同」「スタッフ一同」と書かない）\n"
            "- 本文の最後の一文が、上記固定文末に**自然に繋がる流れ**になるようにする\n"
            "  （感謝・共感・改善姿勢の文 → 固定文末、という流れが理想）\n"
            "- 本文と固定文末を続けて読んだときに、トーン・文体・敬語レベルが**揃って読める**ようにする\n"
        )

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        r_int = int(rating) if rating.isdigit() else 3
        stars = '★' * r_int + '☆' * (5 - r_int)

        prompt = (
            f"あなたは「{business_name}」（業界: {industry}）のオーナーです。\n"
            f"Google マップに投稿されたレビューに対する返信を、**日本語で**書いてください。\n"
            f"{website_section}"
            f"{region_section}"
            f"{seo_section}"
            f"{examples_section}"
            f"{closing_section}\n"
            f"## 返信対象レビュー\n"
            f"レビュアー: {reviewer}\n"
            f"評価: {stars}（{rating}/5）\n"
            f"レビュー本文: {review_body or '（本文なし）'}\n\n"
            f"## 思考ステップ（頭の中で順に行い、結果として「返信本文」だけを出力）\n"
            f"1. このレビューでお客様が**具体的に言及している点**を 2〜3 個抽出する\n"
            f"2. お客様の**感情**（喜び/感謝/不満/具体的指摘）を読み取る\n"
            f"3. 上記 SEO キーワードから、レビュー内容に合わせて**自然に盛り込めるもの**を 1〜2 個選定する\n"
            f"4. 過去返信例があれば、その**言葉遣い・締めの定型・トーン**を継承する\n"
            f"5. お客様の言及点に**具体的に共感**しつつ、SEO キーワードと地域名を自然に織り込んだ返信を書く\n\n"
            f"## ルール（厳守）\n"
            f"1. 必ず日本語・敬語丁寧体\n"
            f"2. {fabrication_rule}\n"
            f"3. お客様が言及した具体的内容に**最低 1 つは触れる**（共感性の演出）\n"
            f"4. SEO キーワードはリスト化せず、文中に**自然に溶け込ませる**\n"
            f"5. 地域名は **多くて 1 回**（不自然な連発は逆効果）\n"
            f"6. 高評価（★4以上）は感謝、低評価（★3以下）は謝罪 + 改善姿勢\n"
            f"7. 過去返信例があれば、その雰囲気を踏襲する\n"
            f"8. 3〜5 文程度、温かみのある自然な文章\n"
            f"9. 出力は**返信本文のみ**（思考過程・前置き・見出し・補足は一切不要）\n"
        )

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        body_text = msg.content[0].text.strip()
        return _append_closing(body_text, closing_phrase)

    except Exception as e:
        print(f"  AI生成失敗（フォールバック使用）: {e}")
        r_int = int(rating) if rating.isdigit() else 3
        if r_int >= 4:
            fallback = (
                "この度はご利用いただき、また素敵なレビューを頂戴し誠にありがとうございます。"
                "お客様にご満足いただけたこと、心より嬉しく思います。"
            )
            if not closing_phrase:
                fallback += "またのご利用を心よりお待ちしております。"
            return _append_closing(fallback, closing_phrase)
        fallback = (
            "この度はご利用いただき、貴重なご意見をいただきありがとうございます。"
            "ご期待に沿えず申し訳ございませんでした。"
            "いただいたご意見をもとにサービスの改善に努めてまいります。"
        )
        return _append_closing(fallback, closing_phrase)


def _append_closing(body: str, closing_phrase: str) -> str:
    """本文の末尾に固定文末を改行つきで付加する。指定が無ければそのまま返す。"""
    if not closing_phrase:
        return body
    return f"{body.rstrip()}\n\n{closing_phrase.strip()}"
