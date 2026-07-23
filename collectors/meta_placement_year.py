"""올해(2026-01-01~오늘) 지면(publisher_platform × platform_position) **연간 집계** → meta_지면_연간.

meta_지면(최근 30일 일별)과 별개. 일별 아닌 기간 집계라 행 수 작음(ad×지면).
실행:  python -m collectors.meta_placement_year
env: META_PLACEMENT_YEAR_SINCE(기본 2026-01-01)
"""
import os
import time
from datetime import date

import pandas as pd

from collectors import config, sheets_io
from collectors.meta_creative_daily import GRAPH, _extract_action, _num, _request

TAB = "meta_지면_연간"
COLUMNS = [
    "since", "until", "campaign_name", "publisher_platform", "platform_position",
    "objective", "ad_id", "ad_name",
    "spend", "impressions", "clicks", "link_clicks",
    "purchase", "offline_purchase", "omni_purchase", "revenue",
]


def fetch(since: str, until: str) -> list[dict]:
    url = f"{GRAPH}/{config.META_API_VERSION}/{config.META_AD_ACCOUNT_ID}/insights"
    params = {
        "level": "ad",
        "breakdowns": "publisher_platform,platform_position",
        "time_range": f'{{"since":"{since}","until":"{until}"}}',  # time_increment 없음 = 기간 집계
        "fields": ",".join([
            "campaign_name", "objective", "ad_id", "ad_name",
            "spend", "impressions", "clicks", "inline_link_clicks",
            "actions", "action_values",
        ]),
        "limit": 500,
        "access_token": config.META_ACCESS_TOKEN,
    }
    rows = []
    while True:
        payload = _request(url, params)
        rows.extend(payload.get("data", []))
        nxt = payload.get("paging", {}).get("next")
        if not nxt:
            break
        url, params = nxt, {}
        time.sleep(1)
    return rows


def run() -> int:
    since = os.environ.get("META_PLACEMENT_YEAR_SINCE", "2026-01-01").strip()
    until = date.today().isoformat()
    print(f"[placement-year] 연간 지면 집계: {since} ~ {until}")
    raw = fetch(since, until)
    out = []
    for row in raw:
        actions = row.get("actions")
        out.append({
            "since": since, "until": until,
            "campaign_name": row.get("campaign_name", ""),
            "publisher_platform": row.get("publisher_platform", ""),
            "platform_position": row.get("platform_position", ""),
            "objective": row.get("objective", ""),
            "ad_id": row.get("ad_id", ""), "ad_name": row.get("ad_name", ""),
            "spend": round(_num(row.get("spend")), 2),
            "impressions": int(_num(row.get("impressions"))),
            "clicks": int(_num(row.get("clicks"))),
            "link_clicks": int(_num(row.get("inline_link_clicks"))),
            "purchase": int(_extract_action(actions, config.PURCHASE_TYPES["purchase"])),
            "offline_purchase": int(_extract_action(actions, config.PURCHASE_TYPES["offline_purchase"])),
            "omni_purchase": int(_extract_action(actions, config.PURCHASE_TYPES["omni_purchase"])),
            "revenue": round(_extract_action(row.get("action_values"), config.REVENUE_TYPES), 2),
        })
    df = pd.DataFrame(out, columns=COLUMNS)
    if not df.empty:
        df = df[df["objective"].isin(config.PURCHASE_OBJECTIVES)]
        purch = df[["purchase", "offline_purchase", "omni_purchase"]].sum(axis=1)
        df = df[(df["spend"] > 0) | (purch > 0)].reset_index(drop=True)
    print(f"[placement-year] {len(df)}행")
    total = sheets_io.write_tab(df, TAB, COLUMNS)
    print(f"[placement-year] 시트 '{TAB}' {total}행 기록")
    return len(df)


if __name__ == "__main__":
    run()
