"""소재매핑 재분류 (1회성).

정책: '오늘 이전' 광고는 사용자 수동 매핑만 인정. 매핑 안 한 광고이름(정크·테스트·
일부러 뺀 것 포함)은 전부 '제외' → 대시보드에서 숨김.
이후 새로 등장하는 광고이름만 수집기가 '자동'으로 등록·표시.

실행(로컬):
  PLAUD_SHEET_ID=... GOOGLE_APPLICATION_CREDENTIALS=/경로/sa.json \
  python -m collectors.reclassify_mapping
"""
import pandas as pd

from collectors import config, creative_mapping, sheets_io


def main() -> None:
    m = sheets_io.read_tab(config.TAB_CREATIVE_MAP, config.CREATIVE_MAP_COLUMNS)
    meta = sheets_io.read_tab(config.TAB_META_CREATIVE_DAILY, config.META_CREATIVE_DAILY_COLUMNS)
    ad_names = set(meta["ad_name"].astype(str).str.strip()) if not meta.empty else set()

    # 기존 '수동'만 인정
    manual = {}
    for _, r in m.iterrows():
        ad = str(r.get("광고이름", "")).strip()
        so = str(r.get("소재", "")).strip()
        if str(r.get("분류방식", "")).strip() == "수동" and ad and so:
            manual[ad] = so

    rows = [{"광고이름": ad, "소재": so, "분류방식": "수동"} for ad, so in manual.items()]
    excluded = sorted((ad_names | set(m["광고이름"].astype(str).str.strip())) - set(manual))
    for ad in excluded:
        if ad and ad != "nan":
            rows.append({"광고이름": ad, "소재": creative_mapping.normalize(ad), "분류방식": "제외"})

    df = pd.DataFrame(rows, columns=config.CREATIVE_MAP_COLUMNS)
    n = sheets_io.write_tab(df, config.TAB_CREATIVE_MAP, config.CREATIVE_MAP_COLUMNS)
    print(f"재분류 완료 — 수동 {len(manual)} · 제외 {n - len(manual)} · 총 {n}행")


if __name__ == "__main__":
    main()
