"""Google 認証

Sheets 用認証は環境に応じて自動切り替え:
  - credentials/service_account.json があれば → サービスアカウント認証（本番運用想定）
  - 無ければ                                  → OAuth フロー（配布版想定）

Business Profile API 用 OAuth は別関数（gmb_client から呼ばれる、現状はメインフロー外）。
"""
from pathlib import Path

from google.oauth2.service_account import Credentials as SACredentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

CREDENTIALS_DIR = Path(__file__).parent / "credentials"
SERVICE_ACCOUNT_FILE = CREDENTIALS_DIR / "service_account.json"
OAUTH_CLIENT_FILE = CREDENTIALS_DIR / "oauth_credentials.json"
OAUTH_TOKEN_SHEETS = CREDENTIALS_DIR / "oauth_token_sheets.json"
OAUTH_TOKEN_GBP = CREDENTIALS_DIR / "oauth_token.json"

SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
GBP_SCOPES = ["https://www.googleapis.com/auth/business.manage"]


def get_credentials():
    """Sheets 用の認証情報を返す。

    サービスアカウントファイルがあれば優先、無ければ OAuth フローで取得する。
    どちらの場合も Sheets スコープを使う。
    """
    if SERVICE_ACCOUNT_FILE.exists():
        return SACredentials.from_service_account_file(
            str(SERVICE_ACCOUNT_FILE), scopes=SHEETS_SCOPES
        )
    return _oauth_flow(SHEETS_SCOPES, OAUTH_TOKEN_SHEETS)


def get_oauth_credentials() -> OAuthCredentials:
    """Business Profile API 用 OAuth 認証情報を返す。"""
    return _oauth_flow(GBP_SCOPES, OAUTH_TOKEN_GBP)


def _oauth_flow(scopes: list[str], token_file: Path) -> OAuthCredentials:
    """共通 OAuth フロー。トークンキャッシュとリフレッシュに対応。"""
    creds = None
    if token_file.exists():
        creds = OAuthCredentials.from_authorized_user_file(str(token_file), scopes)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_file.write_text(creds.to_json())
        return creds

    if not OAUTH_CLIENT_FILE.exists():
        raise FileNotFoundError(
            f"OAuth クライアントファイルが見つかりません: {OAUTH_CLIENT_FILE}"
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH_CLIENT_FILE), scopes)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json())
    return creds
