"""クロスプラットフォーム自動実行登録。

macOS: launchd / Windows: タスクスケジューラ / Linux: cron
sync（新着取得）は30分間隔、post（投稿）は10分間隔で登録する。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
LOGS_DIR = PROJECT_DIR / "logs"

SYNC_LABEL = "com.review-bot.sync"
POST_LABEL = "com.review-bot.post"


def _venv_python() -> str:
    """venv 内の Python 実行ファイルパスを返す。"""
    if sys.platform == "win32":
        p = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
    else:
        p = PROJECT_DIR / ".venv" / "bin" / "python"
    return str(p) if p.exists() else sys.executable


# ------------------------------------------------------------------
# macOS: launchd
# ------------------------------------------------------------------

def _launchd_plist_path(label: str) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"


def _launchd_write(label: str, command: str, interval_sec: int, log_name: str) -> Path:
    LOGS_DIR.mkdir(exist_ok=True)
    plist_path = _launchd_plist_path(label)
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{_venv_python()}</string>
        <string>{PROJECT_DIR / 'main.py'}</string>
        <string>{command}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{PROJECT_DIR}</string>
    <key>StartInterval</key>
    <integer>{interval_sec}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{LOGS_DIR / (log_name + '.log')}</string>
    <key>StandardErrorPath</key>
    <string>{LOGS_DIR / (log_name + '_err.log')}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>BROWSER_HEADLESS</key>
        <string>1</string>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
"""
    plist_path.write_text(plist)
    subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
    subprocess.run(["launchctl", "load", str(plist_path)], check=True)
    return plist_path


def _launchd_remove(label: str) -> None:
    plist_path = _launchd_plist_path(label)
    if plist_path.exists():
        subprocess.run(["launchctl", "unload", str(plist_path)], capture_output=True)
        plist_path.unlink()


# ------------------------------------------------------------------
# Windows: schtasks (XML import で StartWhenAvailable を有効化)
# ------------------------------------------------------------------

def _schtasks_xml(command: str, interval_minutes: int) -> str:
    """Windows タスクスケジューラ用 XML を生成。
    StartWhenAvailable=true により PC がスリープ等で予定時刻を逃した場合、
    起動可能になり次第 catch-up 実行する。
    """
    from datetime import datetime
    py = _venv_python()
    main_py = PROJECT_DIR / "main.py"
    log_path = LOGS_DIR / f"{command}.log"
    start_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    args = (
        f'/c "cd /d &quot;{PROJECT_DIR}&quot; '
        f'&amp;&amp; set BROWSER_HEADLESS=1 '
        f'&amp;&amp; &quot;{py}&quot; &quot;{main_py}&quot; {command} '
        f'&gt;&gt; &quot;{log_path}&quot; 2&gt;&amp;1"'
    )
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Google Review Bot - {command}</Description>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <Repetition>
        <Interval>PT{interval_minutes}M</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>{start_iso}</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions>
    <Exec>
      <Command>cmd.exe</Command>
      <Arguments>{args}</Arguments>
    </Exec>
  </Actions>
</Task>
"""


def _schtasks_create(label: str, command: str, minutes: int) -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    import tempfile
    xml = _schtasks_xml(command, minutes)
    # schtasks の /XML は UTF-16 LE BOM 付き必須
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-16", suffix=".xml", delete=False
    ) as f:
        f.write(xml)
        xml_path = f.name

    # 既存タスクがあれば削除してから登録
    subprocess.run(
        ["schtasks", "/Delete", "/TN", label, "/F"],
        capture_output=True, shell=False,
    )
    subprocess.run(
        ["schtasks", "/Create", "/TN", label, "/XML", xml_path, "/F"],
        check=True,
    )

    try:
        os.unlink(xml_path)
    except OSError:
        pass


def _schtasks_delete(label: str) -> None:
    subprocess.run(
        ["schtasks", "/Delete", "/TN", label, "/F"],
        capture_output=True,
    )


# ------------------------------------------------------------------
# Linux: cron
# ------------------------------------------------------------------

CRON_BEGIN = "# >>> review-bot >>>"
CRON_END = "# <<< review-bot <<<"


def _cron_read() -> str:
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def _cron_write(contents: str) -> None:
    p = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
    p.communicate(contents)


def _cron_strip(existing: str) -> str:
    lines = existing.splitlines()
    out, inside = [], False
    for line in lines:
        if line.strip() == CRON_BEGIN:
            inside = True
            continue
        if line.strip() == CRON_END:
            inside = False
            continue
        if not inside:
            out.append(line)
    return "\n".join(out).rstrip() + "\n" if out else ""


def _cron_install() -> None:
    LOGS_DIR.mkdir(exist_ok=True)
    py = _venv_python()
    main_py = PROJECT_DIR / "main.py"
    existing = _cron_strip(_cron_read())
    # @reboot 行で起動時 catch-up（cron はデフォルトでスリープ中のミスを取り戻さないため）
    block = (
        f"{CRON_BEGIN}\n"
        f"@reboot sleep 30 && cd {PROJECT_DIR} && BROWSER_HEADLESS=1 {py} {main_py} sync "
        f">> {LOGS_DIR}/sync.log 2>&1\n"
        f"*/30 * * * * cd {PROJECT_DIR} && BROWSER_HEADLESS=1 {py} {main_py} sync "
        f">> {LOGS_DIR}/sync.log 2>&1\n"
        f"*/10 * * * * cd {PROJECT_DIR} && BROWSER_HEADLESS=1 {py} {main_py} post "
        f">> {LOGS_DIR}/post.log 2>&1\n"
        f"{CRON_END}\n"
    )
    _cron_write(existing + block)


def _cron_uninstall() -> None:
    _cron_write(_cron_strip(_cron_read()))


# ------------------------------------------------------------------
# 公開 API
# ------------------------------------------------------------------

def install() -> None:
    """OS を判定して自動実行を登録する。"""
    if sys.platform == "darwin":
        _launchd_write(SYNC_LABEL, "sync", 1800, "sync")
        _launchd_write(POST_LABEL, "post", 600, "post")
        print("  macOS: launchd に登録しました")
    elif sys.platform == "win32":
        _schtasks_create(SYNC_LABEL, "sync", 30)
        _schtasks_create(POST_LABEL, "post", 10)
        print("  Windows: タスクスケジューラに登録しました")
    else:
        _cron_install()
        print("  Linux: cron に登録しました")


def uninstall() -> None:
    """自動実行を削除する。"""
    if sys.platform == "darwin":
        _launchd_remove(SYNC_LABEL)
        _launchd_remove(POST_LABEL)
        print("  macOS: launchd から削除しました")
    elif sys.platform == "win32":
        _schtasks_delete(SYNC_LABEL)
        _schtasks_delete(POST_LABEL)
        print("  Windows: タスクスケジューラから削除しました")
    else:
        _cron_uninstall()
        print("  Linux: cron から削除しました")


if __name__ == "__main__":
    cmd = (sys.argv[1:] or ["install"])[0]
    if cmd == "install":
        install()
    elif cmd == "uninstall":
        uninstall()
    else:
        print("使い方: python scheduler.py [install|uninstall]")
        sys.exit(1)
