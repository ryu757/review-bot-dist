@echo off
REM Windows 用 自動実行の停止スクリプト

chcp 65001 >nul
cd /d "%~dp0\システム（触らないでください）"

echo 自動実行を停止します...
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe scheduler.py uninstall
) else (
  python scheduler.py uninstall
)

echo.
pause
