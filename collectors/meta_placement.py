"""Meta insights를 지면(publisher_platform × platform_position)별로 집계 → meta_지면 스냅샷.

포맷(이미지/영상)별 지면 CPM 검증용. 매 실행마다 최근 N일(PLACEMENT_WINDOW_DAYS) 윈도
스냅샷으로 시트를 덮어쓴다(시계열 아님).

실행:  python -m collectors.meta_placement
필요 env: META_ACCESS_TOKEN, META_AD_ACCOUNT_ID, PLAUD_SHEET_ID, GOOGLE_SERVICE_ACCOUNT_JSON
"""
import time
from datetime import date, timedelta

import pandas as pd

from collectors import config, sheets_io
from collectors.meta_creative_daily import GRAPH, _extract_action, _num, _request


def fetch_placement(since: str, until: str) -> list[dict]:
    """act_<id>/insights 를 ad 레벨 + 지면 브레이크다운으로 (윈도 집계) 수집."""
    if not config.META_ACCESS_TOKEN or not config.META_AD_ACCOUNT_ID:
        raise RuntimeError("META_ACCESS_TOKEN / META_AD_ACCOUNT_ID 환경변수 없음.")

    url = f"{GRAPH}/{config.META_API_VERSION}/{config.META_AD_ACCOUNT_ID}/insights"
    params = {
        "level": "ad",
        "breakdowns": "publisher_platform,platform_position",  # 지면 분해
        "time_range": f'{{"since":"{since}","until":"{until}"}}',  # time_increment 없음 = 윈도 집계
        "fields": ",".join([
            "campaign_name", "objective", "ad_id", "ad_name",
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
        url, params = nxt, {}
        time.sleep(1)
    return rows


def transform(raw: list[dict], since: str, until: str) -> pd.DataFrame:
    out = []
    for row in raw:
        spend = _num(row.get("spend"))
        imp = _num(row.get("impressions"))
        clk = _num(row.get("clicks"))
        actions = row.get("actions")
        out.append({
            "window_since": since,
            "window_until": until,
            "publisher_platform": row.get("publisher_platform", ""),
            "platform_position": row.get("platform_position", ""),
            "objective": row.get("objective", ""),
            "ad_id": row.get("ad_id", ""),
            "ad_name": row.get("ad_name", ""),
            "spend": round(spend, 2),
            "impressions": int(imp),
            "clicks": int(clk),
            "link_clicks": int(_num(row.get("inline_link_clicks"))),
            "purchase": int(_extract_action(actions, config.PURCHASE_TYPES["purchase"])),
            "offline_purchase": int(_extract_action(actions, config.PURCHASE_TYPES["offline_purchase"])),
            "omni_purchase": int(_extract_action(actions, config.PURCHASE_TYPES["omni_purchase"])),
            "revenue": round(_extract_action(row.get("action_values"), config.REVENUE_TYPES), 2),
        })
    df = pd.DataFrame(out, columns=config.META_PLACEMENT_COLUMNS)
    if df.empty:
        return df
    # 구매목표 캠페인만 + 지출/구매 있는 행만
    df = df[df["objective"].isin(config.PURCHASE_OBJECTIVES)]
    purch = df[["purchase", "offline_purchase", "omni_purchase"]].sum(axis=1)
    df = df[(df["spend"] > 0) | (purch > 0)]
    return df.reset_index(drop=True)


def run() -> int:
    until = date.today().isoformat()
    since = (date.today() - timedelta(days=config.PLACEMENT_WINDOW_DAYS)).isoformat()
    print(f"[placement] 지면 브레이크다운 수집: {since} ~ {until} (윈도 집계)")
    raw = fetch_placement(since, until)
    print(f"[placement] 원본 {len(raw)}행 (ad×지면)")
    df = transform(raw, since, until)
    print(f"[placement] 필터 후 {len(df)}행 · 지면 {df['publisher_platform'].nunique() if not df.empty else 0}종")
    total = sheets_io.write_tab(df, config.TAB_META_PLACEMENT, config.META_PLACEMENT_COLUMNS)
    print(f"[placement] 시트 '{config.TAB_META_PLACEMENT}' {total}행 기록(스냅샷 덮어씀)")
    return len(df)


if __name__ == "__main__":
    run()
