"""GitHub から最新版を自動取得して上書きするモジュール。

main.py / setup_wizard.py の起動時に check_and_update_silent() を呼ぶことで、
クライアント側で何もしなくても新版に追従できる。

設定: GITHUB_USER と GITHUB_REPO を seinさんが配布前に書き換える。
両方とも空のままだと無効化される（=本番運用環境では何もしない）。

無効化したいとき: 環境変数 DISABLE_AUTO_UPDATE=1 を設定（本番運用 / 開発時用）。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request

# ===== 配布前にここを書き換える =====
GITHUB_USER = "ryu757"
GITHUB_REPO = "review-bot-dist"
GITHUB_BRANCH = "main"
# ====================================

PROJECT_DIR = Path(__file__).resolve().parent
VERSION_FILE = PROJECT_DIR / "VERSION"
REQUIREMENTS_FILE = PROJECT_DIR / "requirements.txt"

# 上書きしてはいけないパス（クライアント固有のデータ・認証情報）
PROTECTED_NAMES = {
    ".env",
    "credentials",
    "google_session",
    "logs",
    ".venv",
    "__pycache__",
    "VERSION",  # 最後に手動更新
}


def is_configured() -> bool:
    return bool(GITHUB_USER and GITHUB_REPO)


def is_disabled() -> bool:
    return os.getenv("DISABLE_AUTO_UPDATE") == "1"


def get_local_version() -> str:
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return "0.0.0"


def _fetch(url: str, timeout: int = 15) -> bytes:
    req = Request(url, headers={"User-Agent": "review-bot-updater/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def get_remote_version() -> str:
    """GitHub の VERSION ファイルから最新バージョンを取得。"""
    if not is_configured():
        return ""
    url = (
        f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/"
        f"{GITHUB_BRANCH}/VERSION"
    )
    try:
        return _fetch(url, timeout=8).decode("utf-8").strip()
    except Exception:
        return ""


def check_and_update_silent() -> bool:
    """サイレントに更新確認・適用。更新があれば True を返す。

    エラーは抑制する（既存版で継続できるようにするため）。
    更新後に呼び出し元が再実行する想定。
    """
    if not is_configured() or is_disabled():
        return False
    try:
        local = get_local_version()
        remote = get_remote_version()
        if not remote or remote == local:
            return False
        print()
        print(f"  📦 更新を検出しました ({local} → {remote})。適用中...")
        _download_and_apply()
        print(f"  ✓ 更新完了 (v{remote})")
        return True
    except Exception as e:
        print(f"  自動更新スキップ: {e}")
        return False


def _download_and_apply() -> None:
    zip_url = (
        f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/archive/refs/heads/"
        f"{GITHUB_BRANCH}.zip"
    )
    data = _fetch(zip_url, timeout=60)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / "update.zip"
        zip_path.write_bytes(data)
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(tmp_path)

        extracted_root = next(tmp_path.glob(f"{GITHUB_REPO}-*"))
        # GitHub zip 内構造: {repo-branch}/システム（触らないでください）/...
        # 配布物の構成と一致するよう、システム配下のファイルだけ上書き
        source_system = _find_system_dir(extracted_root)
        if source_system:
            _overlay(source_system, PROJECT_DIR)
        else:
            # システムフォルダが無い場合、ルート直下のファイルを上書き
            _overlay(extracted_root, PROJECT_DIR)

    # requirements.txt が変わっていれば pip install
    py = _venv_python_path()
    if py.exists():
        try:
            subprocess.run(
                [str(py), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE), "-q"],
                check=False,
                timeout=180,
            )
        except Exception:
            pass

    # VERSION 更新
    new_version = get_remote_version()
    if new_version:
        VERSION_FILE.write_text(new_version)


def _find_system_dir(root: Path) -> Path | None:
    """zip 内から「システム（触らないでください）」サブフォルダを探す。"""
    for p in root.iterdir():
        if p.is_dir() and p.name.startswith("システム"):
            return p
    return None


def _overlay(source: Path, dest: Path) -> None:
    """source 配下を dest に上書きコピー。PROTECTED_NAMES はスキップ。"""
    for item in source.iterdir():
        if item.name in PROTECTED_NAMES:
            continue
        target = dest / item.name
        if item.is_dir():
            target.mkdir(exist_ok=True)
            _overlay(item, target)
        else:
            try:
                shutil.copy2(item, target)
            except Exception:
                pass


def _venv_python_path() -> Path:
    if sys.platform == "win32":
        return PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
    return PROJECT_DIR / ".venv" / "bin" / "python"


def restart_self() -> None:
    """現在のプロセスを同じ引数で再実行（更新後に呼ぶ）。"""
    py = _venv_python_path()
    py_str = str(py) if py.exists() else sys.executable
    os.execv(py_str, [py_str] + sys.argv)
