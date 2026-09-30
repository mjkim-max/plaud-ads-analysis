"""Google Ads API 공용 레이어 (REST searchStream).

- OAuth 토큰 발급 + GAQL 실행을 한 곳에서.
- API 버전은 최신순으로 자동 프로브(404 = 그 버전 만료/미존재 → 다음 시도).
"""
from __future__ import annotations

import requests

from collectors import config

OAUTH_URL = "https://oauth2.googleapis.com/token"
# 최신순 — 구글은 버전을 ~1년 주기로 만료시키므로 신버전을 주기적으로 앞에 추가
CANDIDATE_VERSIONS = ["v25", "v24", "v23", "v22", "v21", "v20"]


def access_token() -> str:
    if not (config.GADS_CLIENT_ID and config.GADS_REFRESH_TOKEN):
        raise RuntimeError("GOOGLE_ADS_CLIENT_ID / REFRESH_TOKEN 환경변수 없음.")
    r = requests.post(OAUTH_URL, data={
        "client_id": config.GADS_CLIENT_ID,
        "client_secret": config.GADS_CLIENT_SECRET,
        "refresh_token": config.GADS_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    }, timeout=60)
    r.raise_for_status()
    return r.json()["access_token"]


def search(query: str) -> list[dict]:
    """GAQL 실행 → results 리스트. 버전 자동 프로브."""
    if not (config.GADS_DEVELOPER_TOKEN and config.GADS_CUSTOMER_ID):
        raise RuntimeError("GOOGLE_ADS_DEVELOPER_TOKEN / CUSTOMER_ID 환경변수 없음.")
    headers = {
        "Authorization": f"Bearer {access_token()}",
        "developer-token": config.GADS_DEVELOPER_TOKEN,
        "Content-Type": "application/json",
    }
    if config.GADS_LOGIN_CUSTOMER_ID:
        headers["login-customer-id"] = config.GADS_LOGIN_CUSTOMER_ID
    versions = ([config.GADS_API_VERSION] if config.GADS_API_VERSION else []) + [
        v for v in CANDIDATE_VERSIONS if v != config.GADS_API_VERSION]
    last_err = None
    for ver in versions:
        url = f"https://googleads.googleapis.com/{ver}/customers/{config.GADS_CUSTOMER_ID}/googleAds:searchStream"
        r = requests.post(url, headers=headers, json={"query": query}, timeout=180)
        if r.status_code == 404:
            last_err = f"{ver}: 404"
            continue
        if r.status_code != 200:
            raise RuntimeError(f"Google Ads API {r.status_code} (ver {ver}): {r.text[:500]}")
        print(f"[gads] API version {ver} 사용")
        results = []
        for batch in r.json():
            results.extend(batch.get("results", []))
        return results
    raise RuntimeError(f"모든 API 버전 404 ({last_err}) — CANDIDATE_VERSIONS에 신버전 추가 필요.")
