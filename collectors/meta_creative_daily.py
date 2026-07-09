"""Meta Marketing API → 소재(ad) 일별 인사이트를 Google Sheets에 적재.

실행:  python -m collectors.meta_creative_daily
필요 env: META_ACCESS_TOKEN, META_AD_ACCOUNT_ID, PLAUD_SHEET_ID,
          GOOGLE_SERVICE_ACCOUNT_JSON (또는 GOOGLE_APPLICATION_CREDENTIALS)
"""
import time
from datetime import date, datetime, timedelta

import pandas as pd
import requests

from collectors import config, creative_mapping, sheets_io

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
            "date_start", "campaign_name", "adset_name", "objective", "ad_id", "ad_name",
            "spend", "impressions", "reach", "frequency", "clicks", "inline_link_clicks",
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
        actions = row.get("actions")
        purchase = _extract_action(actions, config.PURCHASE_TYPES["purchase"])
        offline = _extract_action(actions, config.PURCHASE_TYPES["offline_purchase"])
        omni = _extract_action(actions, config.PURCHASE_TYPES["omni_purchase"])
        revenue = _extract_action(row.get("action_values"), config.REVENUE_TYPES)
        out.append({
            "date": row.get("date_start"),
            "campaign_name": row.get("campaign_name", ""),
            "adset_name": row.get("adset_name", ""),
            "objective": row.get("objective", ""),
            "ad_id": row.get("ad_id", ""),
            "ad_name": row.get("ad_name", ""),
            "spend": round(spend, 2),
            "impressions": int(impressions),
            "reach": int(_num(row.get("reach"))),
            "frequency": round(_num(row.get("frequency")), 3),
            "clicks": int(clicks),
            "link_clicks": int(_num(row.get("inline_link_clicks"))),
            "purchase": int(purchase),
            "offline_purchase": int(offline),
            "omni_purchase": int(omni),
            "revenue": round(revenue, 2),
            "ctr": round(clicks / impressions, 6) if impressions else 0.0,
            "cvr": round(omni / clicks, 6) if clicks else 0.0,   # 전환율=전체구매÷클릭
            "cpa": round(spend / omni, 2) if omni else 0.0,      # CPA=지출÷전체구매
            "cpm": round(spend / impressions * 1000, 2) if impressions else 0.0,
        })
    df = pd.DataFrame(out, columns=config.META_CREATIVE_DAILY_COLUMNS)
    if df.empty:
        return df

    # 어떤 objective가 있는지 로그 (필터 검증용)
    print(f"[meta] objective 분포: {df['objective'].value_counts().to_dict()}")

    # ② 구매목표 캠페인만 유지
    before = len(df)
    df = df[df["objective"].isin(config.PURCHASE_OBJECTIVES)]
    print(f"[meta] 구매목표 필터: {before} → {len(df)}행 (제외 {before - len(df)})")

    # ③ 지출>0 이거나 구매>0 이면 유지 (지출0·구매0만 버림)
    purch_any = df[["purchase", "offline_purchase", "omni_purchase"]].sum(axis=1)
    df = df[(df["spend"] > 0) | (purch_any > 0)]
    print(f"[meta] 지출>0 또는 구매>0: {len(df)}행")

    return df.reset_index(drop=True)


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
    print(f"[meta] 최종 적재 대상 행: {len(df)}")

    # 광고이름 → 소재(정규명) 매핑. 신규 광고는 자동분류 후 소재매핑 탭에 등록.
    mp = creative_mapping.load_map()
    df["소재"], new_rows = creative_mapping.assign(df["ad_name"].tolist(), mp)
    if new_rows:
        sheets_io.append_rows(new_rows, config.TAB_CREATIVE_MAP, config.CREATIVE_MAP_COLUMNS)
        print(f"[meta] 신규 소재매핑 {len(new_rows)}건 자동등록(분류방식=자동)")
    print(f"[meta] 소재매핑 적용: 수동 {len(mp)}건 기준, distinct 소재 {df['소재'].nunique()}개")

    total = sheets_io.upsert_by_date(
        df, config.TAB_META_CREATIVE_DAILY, config.META_CREATIVE_DAILY_COLUMNS)
    print(f"[meta] 시트 '{config.TAB_META_CREATIVE_DAILY}' 총 {total}행 (업서트 완료)")
    return len(df)


if __name__ == "__main__":
    run()
