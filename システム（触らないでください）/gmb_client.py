"""Google Business Profile (My Business) API: レビュー取得・返信投稿"""
from __future__ import annotations

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from auth import get_oauth_credentials
from config import API_DEVELOPER_KEY

# My Business API v4 は標準 discovery に含まれないため URL を指定
MYBUSINESS_DISCOVERY = "https://mybusiness.googleapis.com/$discovery/rest?version=v4"
ACCOUNT_MANAGEMENT_DISCOVERY = (
    "https://mybusinessaccountmanagement.googleapis.com/$discovery/rest?version=v1"
)


def _build_mybusiness(credentials):
    kwargs = {
        "credentials": credentials,
        "discoveryServiceUrl": MYBUSINESS_DISCOVERY,
        "static_discovery": False,
    }
    if API_DEVELOPER_KEY:
        kwargs["developerKey"] = API_DEVELOPER_KEY
    return build("mybusiness", "v4", **kwargs)


def _build_account_management(credentials):
    return build(
        "mybusinessaccountmanagement",
        "v1",
        credentials=credentials,
        discoveryServiceUrl=ACCOUNT_MANAGEMENT_DISCOVERY,
        static_discovery=False,
    )


def list_accounts():
    """ビジネスアカウント一覧を取得。"""
    creds = get_oauth_credentials()
    am = _build_account_management(creds)
    resp = am.accounts().list().execute()
    return resp.get("accounts", [])


def list_locations(account_name: str):
    """指定アカウントの拠点一覧を取得。account_name は 'accounts/123' 形式。"""
    creds = get_oauth_credentials()
    mb = _build_mybusiness(creds)
    locations = []
    page_token = None
    while True:
        req = mb.accounts().locations().list(
            parent=account_name, pageSize=100, pageToken=page_token or ""
        )
        resp = req.execute()
        locations.extend(resp.get("locations", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return locations


def list_reviews(location_name: str):
    """
    指定拠点のレビュー一覧を取得。
    location_name は 'accounts/123/locations/456' 形式。
    返り値: list[dict]（各要素に name, starRating, comment, reviewer, reviewReply 等）
    """
    creds = get_oauth_credentials()
    mb = _build_mybusiness(creds)
    reviews = []
    page_token = None
    while True:
        req = mb.accounts().locations().reviews().list(
            parent=location_name, pageSize=50, pageToken=page_token or ""
        )
        resp = req.execute()
        reviews.extend(resp.get("reviews", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return reviews


def get_all_reviews_with_location_info():
    """
    全アカウント・全拠点のレビューを、(location_name, review) のリストで返す。
    """
    result = []
    for account in list_accounts():
        account_name = account.get("name") or account.get("accountName", "")
        for loc in list_locations(account_name):
            loc_name = loc.get("name") or loc.get("locationName")
            if not loc_name:
                continue
            for review in list_reviews(loc_name):
                result.append((loc_name, review))
    return result


def post_reply(review_name: str, comment: str) -> dict | None:
    """
    指定レビューに返信を投稿（既に返信があれば更新）。
    review_name は 'accounts/xxx/locations/xxx/reviews/xxx' 形式。
    成功時は ReviewReply を返し、失敗時は None を返す（例外は呼び出し元で捕捉可）。
    """
    creds = get_oauth_credentials()
    mb = _build_mybusiness(creds)
    try:
        body = {"comment": comment}
        reply = (
            mb.accounts()
            .locations()
            .reviews()
            .updateReply(name=review_name, body=body)
            .execute()
        )
        return reply
    except HttpError as e:
        if e.resp.status == 404:
            return None
        raise
