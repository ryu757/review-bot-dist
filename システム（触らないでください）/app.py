"""
簡易 Web UI: 下書き一覧を表示し、「確認して投稿」ボタンで返信を投稿する。
  python app.py
  で起動し、ブラウザで http://127.0.0.1:5000 を開く。
"""
from flask import Flask, request, redirect, url_for, render_template_string

from config import STATUS_POSTED
from gmb_client import post_reply
from sheets_client import get_pending_rows_for_display, set_row_status_and_updated

app = Flask(__name__)

INDEX_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>レビュー返信 - 確認して投稿</title>
  <style>
    body { font-family: sans-serif; max-width: 900px; margin: 24px auto; padding: 0 16px; }
    h1 { font-size: 1.25rem; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin-bottom: 16px; }
    .meta { color: #666; font-size: 0.9rem; margin-bottom: 8px; }
    .body { margin: 8px 0; white-space: pre-wrap; }
    .draft { background: #f5f5f5; padding: 12px; border-radius: 6px; margin: 8px 0; white-space: pre-wrap; }
    .btn { display: inline-block; padding: 10px 20px; background: #1a73e8; color: white; text-decoration: none; border-radius: 6px; border: none; cursor: pointer; font-size: 14px; }
    .btn:hover { background: #1557b0; }
    .msg { margin: 12px 0; padding: 10px; border-radius: 6px; }
    .msg.ok { background: #e6f4ea; color: #137333; }
    .msg.err { background: #fce8e6; color: #c5221f; }
    .empty { color: #666; }
  </style>
</head>
<body>
  <h1>レビュー返信 — 下書き確認と投稿</h1>
  {% if message %}
  <p class="msg {{ message.type }}">{{ message.text }}</p>
  {% endif %}
  {% if rows %}
  <p>下書きを確認し、「この内容で投稿」を押すと Google マップに返信が投稿されます。</p>
  {% for r in rows %}
  <div class="card">
    <div class="meta">{{ r.review_date }} · {{ r.reviewer }} · 評価 {{ r.rating }}</div>
    <div class="body"><strong>レビュー:</strong><br>{{ r.body or '（本文なし）' }}</div>
    <div class="draft"><strong>返信下書き:</strong><br>{{ r.draft }}</div>
    <form method="post" action="{{ url_for('post_one', row=r.row) }}" style="margin-top:12px;">
      <button type="submit" class="btn">この内容で投稿</button>
    </form>
  </div>
  {% endfor %}
  {% else %}
  <p class="empty">現在、投稿待ちの下書きはありません。<br><code>python main.py sync</code> で新着レビューを取り込んでください。</p>
  {% endif %}
</body>
</html>
"""


@app.route("/")
def index():
    rows = get_pending_rows_for_display()
    msg_text = request.args.get("msg")
    msg_kind = request.args.get("kind", "ok")
    message = {"text": msg_text, "type": msg_kind} if msg_text else None
    return render_template_string(INDEX_HTML, rows=rows, message=message)


@app.route("/post/<int:row>", methods=["POST"])
def post_one(row: int):
    rows = get_pending_rows_for_display()
    target = next((r for r in rows if r["row"] == row), None)
    if not target:
        return redirect(url_for("index", msg="該当する行が見つかりません。", kind="err"))
    review_name = target["review_name"]
    draft = target["draft"]
    try:
        post_reply(review_name, draft)
        set_row_status_and_updated(row, STATUS_POSTED)
        return redirect(url_for("index", msg="投稿しました。", kind="ok"))
    except Exception as e:
        return redirect(url_for("index", msg=f"投稿に失敗しました: {e}", kind="err"))


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
