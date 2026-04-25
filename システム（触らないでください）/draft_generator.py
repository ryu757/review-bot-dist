"""レビュー返信下書き生成（配布版・日本語専用・Web情報grounding・捏造防止）"""
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
) -> str:
    """レビューに対する日本語の返信下書きを生成。

    ホームページから取得した情報を文脈として渡し、
    そこに書かれていない情報の捏造を厳禁にする。
    """
    business_name = business_name or "（企業名未設定）"
    industry = industry or "（業界未設定）"

    website_text = fetch_website_text(website_url) if website_url else ""

    if website_text:
        website_section = (
            "\n## 自社ホームページから抽出した事実情報（これ以外の情報は推測しないこと）\n"
            f"{website_text}\n"
        )
        fabrication_rule = (
            "**絶対に情報を捏造しない**: 上記ホームページ情報に書かれていない"
            "サービス名・特典・特徴・実績・受賞歴・キャンペーン・スタッフ名・店舗詳細などは"
            "一切使わない。書かれている内容のみ言及する。"
        )
    else:
        website_section = (
            "\n## 自社ホームページの情報: 未取得\n"
            "（具体的なサービス名・特徴には触れないこと）\n"
        )
        fabrication_rule = (
            "**絶対に情報を捏造しない**: 具体的なサービス名・特典・特徴・実績・キャンペーン等は"
            "一切使わない。一般的な感謝・謝罪の表現にとどめる。"
        )

    try:
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        r = int(rating) if rating.isdigit() else 3

        prompt = (
            f"あなたは「{business_name}」（業界: {industry}）のオーナーです。\n"
            f"Google マップに投稿されたレビューに対する返信を、**日本語で**書いてください。"
            f"{website_section}\n"
            f"## 返信対象レビュー\n"
            f"レビュアー: {reviewer}\n"
            f"評価: {'★' * r}{'☆' * (5 - r)}（{rating}/5）\n"
            f"レビュー本文: {review_body or '（本文なし）'}\n\n"
            f"## ルール（厳守）\n"
            f"1. 必ず日本語で返信する（敬語・丁寧体）\n"
            f"2. {fabrication_rule}\n"
            f"3. 不明な情報は曖昧に表現するか触れない（例:「またのご利用」「お客様にご満足いただけるよう」など）\n"
            f"4. 業界（{industry}）でユーザーが検索しそうな自然なキーワードを"
            f"   **ホームページに書かれていれば**1〜2語さりげなく盛り込む（SEO 観点）\n"
            f"5. レビュー本文がある場合は、その内容に具体的に触れる（褒められた点に感謝、不満点に謝罪）\n"
            f"6. 高評価（★4以上）には感謝、低評価（★3以下）には謝罪と改善姿勢を示す\n"
            f"7. 3〜5文程度、温かみのある自然な文章\n"
            f"8. 返信本文のみを出力する（前置き・見出し・補足・「Markdown」のような表現は不要）\n"
        )

        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()

    except Exception as e:
        print(f"  AI生成失敗（フォールバック使用）: {e}")
        r = int(rating) if rating.isdigit() else 3
        if r >= 4:
            return (
                "この度はご利用いただき、また素敵なレビューを頂戴し誠にありがとうございます。"
                "お客様にご満足いただけたこと、心より嬉しく思います。"
                "またのご利用を心よりお待ちしております。"
            )
        return (
            "この度はご利用いただき、貴重なご意見をいただきありがとうございます。"
            "ご期待に沿えず申し訳ございませんでした。"
            "いただいたご意見をもとにサービスの改善に努めてまいります。"
        )
