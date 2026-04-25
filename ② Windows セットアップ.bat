@echo off
REM Windows 用ワンクリック起動スクリプト
REM ダブルクリックするとセットアップが始まります

chcp 65001 >nul
cd /d "%~dp0\システム（触らないでください）"

cls
echo ============================================================
echo   Google レビュー自動返信システム — セットアップ開始
echo ============================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
  echo [エラー] Python がインストールされていません。
  echo.
  echo 以下のページからインストーラをダウンロードしてください:
  echo   https://www.python.org/downloads/
  echo.
  echo インストール時、必ず "Add Python to PATH" にチェックを入れてください。
  echo インストール後、このファイルを再度ダブルクリックしてください。
  echo.
  pause
  exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VERSION=%%v
echo OK Python %PY_VERSION% を検出しました
echo.

python setup_wizard.py
set RC=%errorlevel%

echo.
echo ============================================================
pause
exit /b %RC%
