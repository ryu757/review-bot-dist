@echo off
REM Windows 用：既存の「下書き」を最新ロジックで一括再生成
REM ダブルクリックで実行できます

cd /d "%~dp0\システム（触らないでください）"

echo ============================================================
echo   下書きを最新ロジックで一括再生成します
echo ============================================================
echo.
echo   対象: スプレッドシートの「ステータス＝下書き」の行のみ
echo   影響:
echo     - 設定シートの『固定文末』『重点キーワード』等が反映されます
echo     - 手動で編集した下書きがあれば上書きされます
echo     - 「投稿する」「投稿済み」の行は変更されません
echo     - 下書き10件あたり数円〜十数円のAPI利用料が発生します
echo.

set /p ANS=  続行しますか？ [y/N]:
if /i "%ANS%" NEQ "y" if /i "%ANS%" NEQ "yes" (
  echo   中止しました。
  pause
  exit /b 0
)

echo.
echo   実行中...
echo.

if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe main.py regenerate
) else (
  python main.py regenerate
)

echo.
pause
