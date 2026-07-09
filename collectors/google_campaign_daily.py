"""Google Ads API → 캠페인 일별 (날짜·캠페인·노출·클릭·비용)을 Google Sheets에 적재.

REST 방식(무거운 google-ads SDK 불필요). 소재 단위 X, 캠페인 레벨.
실행:  python -m collectors.google_campaign_daily
필요 env: GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET,
          GOOGLE_ADS_REFRESH_TOKEN, GOOGLE_ADS_CUSTOMER_ID (+ MCC면 GOOGLE_ADS_LOGIN_CUSTOMER_ID),
          PLAUD_SHEET_ID, GOOGLE_SERVICE_ACCOUNT_JSON
"""
from datetime import date, timedelta

import pandas as pd
import requests

from collectors import config, sheets_io

OAUTH_URL = "https://oauth2.googleapis.com/token"
# 최신순 — 404(경로없음)면 다음 버전 시도
CANDIDATE_VERSIONS = ["v21", "v20", "v19", "v18", "v17"]


def _access_token() -> str:
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


def fetch(since: str, until: str) -> list[dict]:
    if not (config.GADS_DEVELOPER_TOKEN and config.GADS_CUSTOMER_ID):
        raise RuntimeError("GOOGLE_ADS_DEVELOPER_TOKEN / CUSTOMER_ID 환경변수 없음.")
    headers = {
        "Authorization": f"Bearer {_access_token()}",
        "developer-token": config.GADS_DEVELOPER_TOKEN,
        "Content-Type": "application/json",
    }
    if config.GADS_LOGIN_CUSTOMER_ID:
        headers["login-customer-id"] = config.GADS_LOGIN_CUSTOMER_ID
    query = (
        "SELECT segments.date, campaign.name, metrics.impressions, "
        "metrics.clicks, metrics.cost_micros FROM campaign "
        f"WHERE segments.date BETWEEN '{since}' AND '{until}'"
    )
    # 설정 버전 먼저, 404면 최신순으로 자동 시도
    versions = [config.GADS_API_VERSION] + [v for v in CANDIDATE_VERSIONS if v != config.GADS_API_VERSION]
    for ver in versions:
        url = f"https://googleads.googleapis.com/{ver}/customers/{config.GADS_CUSTOMER_ID}/googleAds:searchStream"
        r = requests.post(url, headers=headers, json={"query": query}, timeout=180)
        if r.status_code == 404:
            continue  # 그 버전 경로 없음 → 다음
        if r.status_code != 200:
            raise RuntimeError(f"Google Ads API {r.status_code} (ver {ver}): {r.text[:500]}")
        print(f"[google] API version {ver} 사용")
        results = []
        for batch in r.json():
            results.extend(batch.get("results", []))
        return results
    raise RuntimeError("모든 API 버전에서 404 — 유효한 GOOGLE_ADS_API_VERSION 확인 필요.")


def transform(raw: list[dict]) -> pd.DataFrame:
    out = []
    for res in raw:
        met = res.get("metrics", {})
        out.append({
            "date": res.get("segments", {}).get("date"),
            "campaign_name": res.get("campaign", {}).get("name", ""),
            "impressions": int(met.get("impressions", 0) or 0),
            "clicks": int(met.get("clicks", 0) or 0),
            "cost": round(int(met.get("costMicros", 0) or 0) / 1e6, 2),
        })
    df = pd.DataFrame(out, columns=config.GOOGLE_DAILY_COLUMNS)
    if df.empty:
        return df
    # 캠페인×일자 합산(중복 방지)
    df = df.groupby(["date", "campaign_name"], as_index=False).agg(
        impressions=("impressions", "sum"), clicks=("clicks", "sum"), cost=("cost", "sum"))
    return df[df["impressions"] + df["clicks"] + df["cost"] > 0].reset_index(drop=True)


def run(since: str = "", until: str = "") -> int:
    since = since or config.META_SINCE
    until = until or config.META_UNTIL
    if not until:
        until = date.today().isoformat()
    if not since:
        since = (date.today() - timedelta(days=config.LOOKBACK_DAYS)).isoformat()

    print(f"[google] 캠페인 일별 수집: {since} ~ {until}")
    df = transform(fetch(since, until))
    print(f"[google] 캠페인-일 행: {len(df)}")
    total = sheets_io.upsert_by_date(df, config.TAB_GOOGLE_DAILY, config.GOOGLE_DAILY_COLUMNS)
    print(f"[google] 시트 '{config.TAB_GOOGLE_DAILY}' 총 {total}행 (업서트 완료)")
    return len(df)


if __name__ == "__main__":
    run()
