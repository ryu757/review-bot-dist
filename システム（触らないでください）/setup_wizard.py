"""対話式セットアップウィザード（配布版・3アクション体験）

クライアントが行う実質的な操作は：
  1. setup.command をダブルクリック
  2. 自動で開かれるスプレッドシートに 4 項目を入力
  3. Google ビジネスプロフィールにログイン

それ以外はウィザードが極力自動でやる：
- 仮想環境構築・依存インストール
- ~/Downloads から OAuth JSON を自動検出
- スプレッドシートを自動作成（必要に応じて）
- 設定シートを自動作成して入力欄を準備
- ホームページ取得テスト
- 自動実行登録
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
VENV_DIR = PROJECT_DIR / ".venv"
ENV_FILE = PROJECT_DIR / ".env"
CREDENTIALS_DIR = PROJECT_DIR / "credentials"
OAUTH_CLIENT_FILE = CREDENTIALS_DIR / "oauth_credentials.json"
OAUTH_TOKEN_SHEETS = CREDENTIALS_DIR / "oauth_token_sheets.json"
SESSION_DIR = PROJECT_DIR / "google_session"


# ------------------------------------------------------------------
# 表示ヘルパー
# ------------------------------------------------------------------

def _line(char: str = "─") -> None:
    print(char * 60)


def _step(num: int, total: int, title: str) -> None:
    print()
    _line("═")
    print(f"  ステップ {num}/{total}  {title}")
    _line("═")


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"  {prompt}{suffix}: ").strip()
    return val or default


def _yesno(prompt: str, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    val = input(f"  {prompt} [{d}]: ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes")


def _open_url(url: str) -> None:
    print(f"  ブラウザで開きます: {url}")
    try:
        webbrowser.open(url)
    except Exception:
        pass


# ------------------------------------------------------------------
# venv ブートストラップ
# ------------------------------------------------------------------

def _venv_python() -> Path:
    if sys.platform == "win32":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _in_target_venv() -> bool:
    """現在の Python がプロジェクトの venv 内かを判定。

    Japanese パスの Unicode 正規化（NFC vs NFD）の差で文字列比較が失敗するケースがあるため、
    inode 比較の os.path.samefile を使う。
    """
    try:
        if sys.prefix == sys.base_prefix:
            return False
        return os.path.samefile(sys.prefix, str(VENV_DIR))
    except (OSError, FileNotFoundError):
        return False


def _bootstrap_venv() -> None:
    if not VENV_DIR.exists():
        print("  仮想環境を作成中...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)

    py = str(_venv_python())
    print("  pip を更新中...")
    subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip", "-q"], check=True)

    print("  依存ライブラリをインストール中...（数分かかることがあります）")
    subprocess.run(
        [py, "-m", "pip", "install", "-r", str(PROJECT_DIR / "requirements.txt"), "-q"],
        check=True,
    )

    print("  ブラウザコンポーネント (Chromium) をインストール中...（数分かかることがあります）")
    subprocess.run([py, "-m", "playwright", "install", "chromium"], check=True)


# ------------------------------------------------------------------
# .env 操作
# ------------------------------------------------------------------

def _read_env() -> dict:
    out = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip()
    return out


def _write_env(values: dict) -> None:
    ENV_FILE.write_text("".join(f"{k}={v}\n" for k, v in values.items()))


# ------------------------------------------------------------------
# 各ステップ
# ------------------------------------------------------------------

def _step_oauth_client() -> None:
    """OAuth クライアント JSON の準備。~/Downloads から自動検出を試みる。"""
    CREDENTIALS_DIR.mkdir(exist_ok=True)
    if OAUTH_CLIENT_FILE.exists():
        if _yesno("既存の OAuth クライアントを使い続けますか？", True):
            print("  既存のものを使用します")
            return
        OAUTH_CLIENT_FILE.unlink()

    # ~/Downloads から自動検出
    downloads = Path.home() / "Downloads"
    candidates = sorted(
        downloads.glob("client_secret_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if candidates:
        latest = candidates[0]
        print()
        print(f"  ダウンロードフォルダで OAuth クライアント JSON を見つけました:")
        print(f"    {latest.name}")
        if _yesno("  これを使いますか？", True):
            shutil.copy(latest, OAUTH_CLIENT_FILE)
            print(f"  ✓ コピーしました")
            return

    # 自動検出に失敗 or ユーザーが拒否 → ガイド付きで作成
    _guided_oauth_client_creation(downloads)


def _guided_oauth_client_creation(downloads: Path) -> None:
    """Google Cloud Console で必要なページを順番に自動オープンしながら、
    OAuth クライアント JSON を作成・取得する対話式フロー。"""
    print()
    print("  これから Google Cloud Console で「OAuth クライアント」を作成します。")
    print("  必要なページを順番に自動で開きますので、画面の指示通りに操作してください。")
    print("  （Google アカウントへのログインを求められたら自分のアカウントでログインしてください）")
    print()
    input("  準備ができたら ENTER を押してください...")

    # --- 小ステップ 1/4: プロジェクト作成 ---
    print()
    _line("─")
    print("  小ステップ 1/4  プロジェクトを作成")
    _line("─")
    _open_url("https://console.cloud.google.com/projectcreate")
    print()
    print("  ▼ 開いたページでやること:")
    print("    ① 「プロジェクト名」に好きな名前を入力(例: review-bot)")
    print("    ② 「場所」はそのままで OK")
    print("    ③ 「作成」ボタンをクリック")
    print("    ④ 画面右上の通知でプロジェクト作成完了を待つ(数秒〜十数秒)")
    print()
    input("  完了したら ENTER を押してください...")

    # --- 小ステップ 2/4: Sheets API 有効化 ---
    print()
    _line("─")
    print("  小ステップ 2/4  Google Sheets API を有効化")
    _line("─")
    _open_url("https://console.cloud.google.com/apis/library/sheets.googleapis.com")
    print()
    print("  ▼ 開いたページでやること:")
    print("    ① 画面上部のプロジェクト選択が、さきほど作ったプロジェクトかを確認")
    print("       (違っていたら上部メニューから切り替え)")
    print("    ② 青い「有効にする」ボタンをクリック")
    print("    ③ ダッシュボードに切り替わるまで待つ")
    print()
    input("  完了したら ENTER を押してください...")

    # --- 小ステップ 3/4: OAuth 同意画面 ---
    print()
    _line("─")
    print("  小ステップ 3/4  OAuth 同意画面を設定")
    _line("─")
    _open_url("https://console.cloud.google.com/apis/credentials/consent")
    print()
    print("  ▼ 開いたページでやること:")
    print("    ① 「User Type」で『外部』を選び「作成」")
    print("    ② アプリ名: 好きな名前(例: review-bot)")
    print("    ③ ユーザーサポートメール: 自分の Google メールを選択")
    print("    ④ デベロッパー連絡先情報: 自分のメールアドレスを入力")
    print("    ⑤ 「保存して次へ」を3回押して進む(スコープ・テストユーザーは空のまま)")
    print("    ⑥ 完了後、左メニュー(または「対象」)から「テストユーザー」を開く")
    print("    ⑦ 「+ ADD USERS」を押して、自分の Google メールを追加 → 保存")
    print()
    input("  完了したら ENTER を押してください...")

    # --- 小ステップ 4/4: OAuth クライアント ID 作成 & JSON ダウンロード ---
    print()
    _line("─")
    print("  小ステップ 4/4  OAuth クライアント ID を作成 & JSON ダウンロード")
    _line("─")
    _open_url("https://console.cloud.google.com/apis/credentials/oauthclient")
    print()
    print("  ▼ 開いたページでやること:")
    print("    ① 「アプリケーションの種類」→『デスクトップアプリ』を選択")
    print("    ② 「名前」: 好きな名前(例: review-bot-desktop)")
    print("    ③ 「作成」ボタンをクリック")
    print("    ④ ポップアップで『JSON をダウンロード』ボタンをクリック")
    print("       (ダウンロードフォルダに client_secret_xxx.json が保存される)")
    print()
    print("  JSON のダウンロードが終わったら、ENTER を押してください。")
    print("  自動でダウンロードフォルダから検出します。")

    while True:
        input("  ENTER を押してください...")
        candidates = sorted(
            downloads.glob("client_secret_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            latest = candidates[0]
            shutil.copy(latest, OAUTH_CLIENT_FILE)
            print(f"  ✓ {latest.name} を取り込みました")
            return
        print(f"  × ダウンロードフォルダに client_secret_*.json が見つかりません")
        if not _yesno("  もう一度確認しますか？", True):
            raise SystemExit("OAuth クライアント JSON が必要です。中断します。")


def _step_oauth_consent() -> None:
    if OAUTH_TOKEN_SHEETS.exists():
        if _yesno("既存の Google アカウント認可を使い続けますか？", True):
            print("  既存の認可を使用します")
            return
        OAUTH_TOKEN_SHEETS.unlink()

    print()
    print("  ブラウザを開いて Google アカウントでスプレッドシートへのアクセスを許可してください。")
    input("  ENTER を押すと開きます...")

    sys.path.insert(0, str(PROJECT_DIR))
    from auth import get_credentials  # type: ignore

    get_credentials()
    print("  ✓ 認可完了")


def _reload_config_modules() -> None:
    """SPREADSHEET_ID 変更後、config と sheets_client をリロードして反映させる。"""
    import importlib
    try:
        import config  # type: ignore
        importlib.reload(config)
    except Exception:
        pass
    try:
        import sheets_client  # type: ignore
        importlib.reload(sheets_client)
    except Exception:
        pass


def _step_spreadsheet_setup() -> None:
    """スプレッドシートの作成 or 既存指定。"""
    sys.path.insert(0, str(PROJECT_DIR))
    from sheets_client import create_new_spreadsheet  # type: ignore

    env = _read_env()
    if env.get("SPREADSHEET_ID"):
        if _yesno(
            f"既存スプレッドシート ({env['SPREADSHEET_ID'][:20]}...) を使い続けますか？",
            True,
        ):
            print("  既存スプレッドシートを使用します")
            os.environ["SPREADSHEET_ID"] = env["SPREADSHEET_ID"]
            _reload_config_modules()
            return

    print()
    if _yesno("新規スプレッドシートを自動作成しますか？", True):
        print("  作成中...")
        spreadsheet_id, url = create_new_spreadsheet()
        env["SPREADSHEET_ID"] = spreadsheet_id
        _write_env(env)
        print(f"  ✓ 作成しました")
        print(f"    URL: {url}")
        print("    （あとで Google Drive で好きなフォルダに移動できます）")
    else:
        print()
        print("  既存のスプレッドシート ID を入力してください。")
        print("  https://docs.google.com/spreadsheets/d/【ここがID】/edit")
        print()
        spreadsheet_id = _ask("スプレッドシート ID")
        if not spreadsheet_id:
            raise SystemExit("スプレッドシート ID が必要です。中断します。")
        env["SPREADSHEET_ID"] = spreadsheet_id
        _write_env(env)

    # .env 書き込み後、後続ステップが参照するモジュール内の SPREADSHEET_ID を即時更新
    os.environ["SPREADSHEET_ID"] = spreadsheet_id
    _reload_config_modules()


def _step_init_sheets() -> None:
    """スプレッドシートに 2 タブとヘッダーを作成。"""
    sys.path.insert(0, str(PROJECT_DIR))
    from sheets_client import ensure_sheet_ready  # type: ignore

    print()
    print("  スプレッドシートを初期化します（『レビュー返信』『設定』タブを作成）...")
    ensure_sheet_ready()
    print("  ✓ 初期化完了")


def _guided_anthropic_key_creation() -> None:
    """Anthropic Console を開き、API キー作成手順を案内する。"""
    print()
    _line("─")
    print("  Anthropic API キーを作成")
    _line("─")
    _open_url("https://console.anthropic.com/settings/keys")
    print()
    print("  ▼ 開いたページでやること:")
    print("    ① 未ログインなら Google アカウント等でログイン")
    print("       (初回はクレジットカード登録 → クレジットチャージが必要)")
    print("    ② 「Create Key」ボタンをクリック")
    print("    ③ キーの名前: 好きな名前(例: review-bot)")
    print("    ④ 表示された『sk-ant-...』で始まるキーを必ずコピー")
    print("       ※ このキーは作成時しか表示されません。必ずコピーしてください")
    print()
    print("  キーをコピーできたら、次でスプレッドシートに貼り付けます。")
    input("  ENTER を押して次へ...")


def _step_fill_config_in_sheet() -> None:
    """ユーザーに設定シートを開いてもらい、4 項目を入力してもらう。"""
    sys.path.insert(0, str(PROJECT_DIR))
    from sheets_client import get_business_config, get_config_sheet_url  # type: ignore
    from config import (  # type: ignore
        CONFIG_KEY_BUSINESS_NAME,
        CONFIG_KEY_INDUSTRY,
        CONFIG_KEY_WEBSITE_URL,
        CONFIG_KEY_ANTHROPIC_KEY,
        CONFIG_KEY_CLOSING_PHRASE,
        REQUIRED_CONFIG_KEYS,
    )

    # 先に Anthropic API キー取得をガイド (既に持っている場合はスキップ)
    if not _yesno("Anthropic API キーは既にお持ちですか？", False):
        _guided_anthropic_key_creation()

    url = get_config_sheet_url()
    print()
    print("  スプレッドシートの『設定』タブを開きます。以下の項目を入力してください:")
    print()
    print(f"  【必須】")
    print(f"    • {CONFIG_KEY_BUSINESS_NAME}     例: 株式会社サンプル")
    print(f"    • {CONFIG_KEY_INDUSTRY}         例: 飲食店、美容室、自動車販売")
    print(f"    • {CONFIG_KEY_ANTHROPIC_KEY}  先ほどコピーした『sk-ant-...』のキー")
    print(f"  【任意】")
    print(f"    • {CONFIG_KEY_WEBSITE_URL}  例: https://example.com")
    print(f"    • {CONFIG_KEY_CLOSING_PHRASE}      例: またのご来店を心よりお待ちしております。")
    print(f"                  ※ 入力すると、全ての返信の末尾にこの定型文が必ず付加されます")
    print()
    if _yesno("  スプレッドシートを開きますか？", True):
        _open_url(url)
    print()

    while True:
        input("  入力が完了したら ENTER を押してください...")
        # キャッシュクリアして最新値取得
        import sheets_client  # type: ignore
        sheets_client._CACHED_CONFIG = None
        config = get_business_config()

        missing = [k for k in REQUIRED_CONFIG_KEYS if not config.get(k)]
        api_key = config.get(CONFIG_KEY_ANTHROPIC_KEY, "")
        invalid_key = api_key and not api_key.startswith("sk-ant-")

        if not missing and not invalid_key:
            break

        if missing:
            print(f"  ⚠ 未入力の項目があります: {', '.join(missing)}")
        if invalid_key:
            print(f"  ⚠ Anthropic APIキーは『sk-ant-』で始まる必要があります")
        print(f"  もう一度スプレッドシートで入力してから ENTER を押してください。")
        print(f"  シート URL: {url}")

    # API キーを .env にコピー（runtime で anthropic.Anthropic() が読む）
    env = _read_env()
    env["ANTHROPIC_API_KEY"] = api_key
    _write_env(env)
    print("  ✓ 設定値を読み取りました")

    # ホームページ取得テスト
    website_url = config.get(CONFIG_KEY_WEBSITE_URL, "")
    if website_url:
        print()
        print("  ホームページ情報を取得します...")
        from website_fetcher import fetch_website_text  # type: ignore
        text = fetch_website_text(website_url, force=True)
        if text:
            print(f"  ✓ {len(text)} 文字の情報を取得・キャッシュしました")
        else:
            print("  ⚠ ホームページから情報を取得できませんでした")
            print("    URL が正しいか、サイトがアクセス可能かをご確認ください")


def _step_business_login() -> None:
    if SESSION_DIR.exists() and (SESSION_DIR / "state.json").exists():
        if _yesno("既存の Google ビジネスプロフィールのログインセッションを使い続けますか？", True):
            print("  既存のセッションを使用します")
            return
        shutil.rmtree(SESSION_DIR, ignore_errors=True)

    print()
    print("  ブラウザを開きます。Google ビジネスプロフィールにログインしてください。")
    print("  ログイン完了後、ブラウザを閉じれば OK です。")
    print("  （5分待つと自動でブラウザが閉じます）")
    input("  ENTER を押すと開きます...")

    sys.path.insert(0, str(PROJECT_DIR))
    os.environ["BROWSER_HEADLESS"] = "0"
    from browser_client import login_interactive  # type: ignore

    login_interactive()
    print("  ✓ ログインセッションを保存しました")


def _step_schedule() -> None:
    if not _yesno("自動実行を登録しますか？（30分ごとに新着取得・10分ごとに投稿）", True):
        print("  スキップしました（後で `python scheduler.py install` で登録できます）")
        return

    sys.path.insert(0, str(PROJECT_DIR))
    from scheduler import install  # type: ignore
    install()


def _step_initial_run() -> None:
    """セットアップ完了直後に最初の sync を実行して動作確認させる。"""
    print()
    print("  最初のレビュー取得を実行して、スプレッドシートに下書きを書き込みます。")
    print("  （新着レビューが多いと数分かかることがあります）")
    if not _yesno("今すぐ実行しますか？", True):
        print("  スキップしました。最初の自動実行は 30 分後です。")
        return

    py = str(_venv_python())
    main_py = PROJECT_DIR / "main.py"
    print()
    print("  実行中...")
    rc = subprocess.run([py, str(main_py), "sync"]).returncode
    if rc == 0:
        print()
        print("  ✓ 初回取得が完了しました。スプレッドシートを確認してください。")
    else:
        print()
        print("  ⚠ 取得中にエラーが発生しました。ログを確認してください。")
        print("  （セッション切れの可能性があります。エラーメッセージを配布元に共有してください）")


# ------------------------------------------------------------------
# main
# ------------------------------------------------------------------

def main() -> None:
    print()
    _line("═")
    print("  Google レビュー自動返信システム — セットアップウィザード")
    _line("═")
    print()
    print("  クライアントが行う操作は実質 3 つです:")
    print("    ① OAuth クライアント JSON の準備（自動検出を試みます）")
    print("    ② スプレッドシートに 4 項目を入力（自動で開かれます）")
    print("    ③ Google ビジネスプロフィールにログイン（ブラウザで）")

    # ステップ 0: venv とライブラリ
    # （無限ループ防止: 既に bootstrap 済みなら環境変数で2度目をスキップ）
    bootstrapped = os.getenv("WIZARD_BOOTSTRAPPED") == "1"
    if not _in_target_venv() and not bootstrapped:
        _step(0, 8, "仮想環境と依存ライブラリの準備")
        _bootstrap_venv()

        py = str(_venv_python())
        print()
        print("  仮想環境内でウィザードを再起動します...")
        time.sleep(1)
        env = {**os.environ, "WIZARD_BOOTSTRAPPED": "1"}
        rc = subprocess.run([py, str(Path(__file__).resolve())], env=env).returncode
        sys.exit(rc)

    # venv 内で起動後、GitHub 上の最新版を自動取得
    sys.path.insert(0, str(PROJECT_DIR))
    try:
        import auto_update  # type: ignore
        if auto_update.check_and_update_silent():
            print("  ウィザードを再起動します...")
            time.sleep(1)
            auto_update.restart_self()
    except ImportError:
        pass

    _step(1, 8, "OAuth クライアント JSON の準備")
    _step_oauth_client()

    _step(2, 8, "Google アカウントの認可")
    _step_oauth_consent()

    _step(3, 8, "スプレッドシート作成")
    _step_spreadsheet_setup()

    _step(4, 8, "スプレッドシート初期化（タブ作成）")
    _step_init_sheets()

    _step(5, 8, "事業情報・APIキーをスプレッドシートに入力")
    _step_fill_config_in_sheet()

    _step(6, 8, "Google ビジネスプロフィールへのログイン")
    _step_business_login()

    _step(7, 8, "自動実行の登録")
    _step_schedule()

    _step(8, 8, "初回レビュー取得（動作確認）")
    _step_initial_run()

    print()
    _line("═")
    print("  セットアップ完了！")
    _line("═")
    print()
    print("  運用方法:")
    print("    ・新着レビューは 30 分ごとに自動でスプレッドシートに追加されます")
    print("    ・スプレッドシートで「ステータス」を「投稿する」に変更すると、")
    print("      10 分以内に自動で Google マップに返信が投稿されます")
    print("    ・企業情報・ホームページURL・APIキーは『設定』タブで変更できます")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  中断しました")
        sys.exit(130)
    except Exception as e:
        print()
        print(f"  エラー: {e}")
        print("  README のトラブルシューティングを参照してください。")
        sys.exit(1)
