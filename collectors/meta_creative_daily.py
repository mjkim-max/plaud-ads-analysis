"""Meta Marketing API → 소재(ad) 일별 인사이트를 Google Sheets에 적재.

실행:  python -m collectors.meta_creative_daily
필요 env: META_ACCESS_TOKEN, META_AD_ACCOUNT_ID, PLAUD_SHEET_ID,
          GOOGLE_SERVICE_ACCOUNT_JSON (또는 GOOGLE_APPLICATION_CREDENTIALS)
"""
import time
from datetime import date, datetime, timedelta

import pandas as pd
import requests

from collectors import config, sheets_io

GRAPH = "https://graph.facebook.com"


def _month_ranges(since: str, until: str):
    """[since, until] 을 월 단위 (since, until) 청크로 분할."""
    start = datetime.strptime(since, "%Y-%m-%d").date()
    end = datetime.strptime(until, "%Y-%m-%d").date()
    cur = start
    while cur <= end:
        nxt = date(cur.year + 1, 1, 1) if cur.month == 12 else date(cur.year, cur.month + 1, 1)
        yield cur.isoformat(), min(nxt - timedelta(days=1), end).isoformat()
        cur = nxt


# Meta 레이트리밋 관련 에러코드 (백오프 재시도 대상)
RATE_LIMIT_CODES = {4, 17, 32, 613, 80000, 80001, 80002, 80003, 80004, 80005, 80006, 80008}


def _request(url: str, params: dict) -> dict:
    """레이트리밋(403/429/5xx/Meta 코드)에 지수 백오프로 대응하는 GET."""
    for attempt in range(6):
        r = requests.get(url, params=params, timeout=120)
        if r.status_code == 200:
            return r.json()
        err = {}
        try:
            err = r.json().get("error", {}) or {}
        except Exception:
            pass
        code = err.get("code")
        retryable = (
            r.status_code in (403, 429, 500, 503)
            or code in RATE_LIMIT_CODES
            or "rate limit" in str(err.get("message", "")).lower()
        )
        if retryable and attempt < 5:
            wait = min(60 * (attempt + 1), 300)  # 60→300s
            print(f"[meta] {r.status_code}/code={code} 레이트리밋 → {wait}s 대기 후 재시도 ({attempt + 1}/5)")
            time.sleep(wait)
            continue
        raise RuntimeError(f"Meta API {r.status_code} code={code} msg={err.get('message')}")
    raise RuntimeError("Meta API 재시도 소진")


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _extract_action(actions, types) -> float:
    """actions 리스트에서 우선순위상 처음 발견되는 action_type의 value 합."""
    if not isinstance(actions, list):
        return 0.0
    by_type = {a.get("action_type"): _num(a.get("value")) for a in actions}
    for t in types:
        if t in by_type:
            return by_type[t]
    return 0.0


def fetch_insights(since: str, until: str) -> list[dict]:
    """act_<id>/insights 를 ad 레벨·일별로 페이징하며 수집."""
    if not config.META_ACCESS_TOKEN or not config.META_AD_ACCOUNT_ID:
        raise RuntimeError("META_ACCESS_TOKEN / META_AD_ACCOUNT_ID 환경변수 없음.")

    url = f"{GRAPH}/{config.META_API_VERSION}/{config.META_AD_ACCOUNT_ID}/insights"
    params = {
        "level": "ad",
        "time_increment": 1,
        "time_range": f'{{"since":"{since}","until":"{until}"}}',
        "fields": ",".join([
            "date_start", "campaign_name", "adset_name", "ad_id", "ad_name",
            "spend", "impressions", "clicks", "inline_link_clicks",
            "actions", "action_values",
        ]),
        "limit": 500,
        "access_token": config.META_ACCESS_TOKEN,
    }

    rows: list[dict] = []
    while True:
        payload = _request(url, params)
        rows.extend(payload.get("data", []))
        nxt = payload.get("paging", {}).get("next")
        if not nxt:
            break
        url, params = nxt, {}  # next URL은 파라미터가 이미 포함됨
        time.sleep(1)  # 페이지 간 간격 (레이트리밋 예방)
    return rows


def transform(raw: list[dict]) -> pd.DataFrame:
    out = []
    for row in raw:
        spend = _num(row.get("spend"))
        impressions = _num(row.get("impressions"))
        clicks = _num(row.get("clicks"))
        purchases = _extract_action(row.get("actions"), config.PURCHASE_ACTION_TYPES)
        revenue = _extract_action(row.get("action_values"), config.PURCHASE_ACTION_TYPES)
        out.append({
            "date": row.get("date_start"),
            "campaign_name": row.get("campaign_name", ""),
            "adset_name": row.get("adset_name", ""),
            "ad_id": row.get("ad_id", ""),
            "ad_name": row.get("ad_name", ""),
            "spend": round(spend, 2),
            "impressions": int(impressions),
            "clicks": int(clicks),
            "link_clicks": int(_num(row.get("inline_link_clicks"))),
            "purchases": int(purchases),
            "revenue": round(revenue, 2),
            "ctr": round(clicks / impressions, 6) if impressions else 0.0,
            "cvr": round(purchases / clicks, 6) if clicks else 0.0,
            "cpa": round(spend / purchases, 2) if purchases else 0.0,
            "cpm": round(spend / impressions * 1000, 2) if impressions else 0.0,
        })
    df = pd.DataFrame(out, columns=config.META_CREATIVE_DAILY_COLUMNS)
    # 지출 없는 행 제외 (스키마: 지출>0 기준)
    return df[df["spend"] > 0].reset_index(drop=True)


def run(since: str = "", until: str = "") -> int:
    since = since or config.META_SINCE
    until = until or config.META_UNTIL
    if not until:
        until = date.today().isoformat()
    if not since:
        since = (date.today() - timedelta(days=config.LOOKBACK_DAYS)).isoformat()

    print(f"[meta] insights 수집: {since} ~ {until} (월 단위 청크)")
    raw: list[dict] = []
    for m_since, m_until in _month_ranges(since, until):
        chunk = fetch_insights(m_since, m_until)
        print(f"[meta]   {m_since}~{m_until}: {len(chunk)}행")
        raw.extend(chunk)
        time.sleep(2)  # 청크 간 간격 (레이트리밋 예방)
    df = transform(raw)
    print(f"[meta] 지출>0 소재-일 행: {len(df)}")

    total = sheets_io.upsert_by_date(
        df, config.TAB_META_CREATIVE_DAILY, config.META_CREATIVE_DAILY_COLUMNS)
    print(f"[meta] 시트 '{config.TAB_META_CREATIVE_DAILY}' 총 {total}행 (업서트 완료)")
    return len(df)


if __name__ == "__main__":
    run()
