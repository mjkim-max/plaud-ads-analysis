"""광고 → 게시물 ID 캐시 (소재_게시물ID 탭).

같은 게시물 ID = 같은 소재. 광고 크리에이티브 조회는 무거워서(레이트리밋)
매일 전체를 다시 부르지 않고, 탭에 없는 새 ad_id만 50개씩 묶어 조회해 추가한다.

게시물 ID 우선순위: 원본 인스타 게시물(파트너십 광고코드) → 업로드 영상 → 이미지 해시
→ 광고 인스타 게시물(기존 게시물 사용 광고). 앞 접두어(ig/vid/img/eig)로 종류 구분.
"""
from __future__ import annotations

import time

from collectors import config, sheets_io

GRAPH = "https://graph.facebook.com"
FIELDS = "creative{source_instagram_media_id,video_id,image_hash,effective_instagram_media_id}"
KEY_FIELDS = [
    ("source_instagram_media_id", "ig"),
    ("video_id", "vid"),
    ("image_hash", "img"),
    ("effective_instagram_media_id", "eig"),
]


def post_key(creative: dict) -> str:
    for field, tag in KEY_FIELDS:
        if creative.get(field):
            return f"{tag}:{creative[field]}"
    return ""


def sync(ads: dict, request) -> dict:
    """ads: {ad_id: 광고이름}. 캐시에 없는 ad_id만 Meta에서 조회해 탭에 추가.
    request: meta_creative_daily._request (백오프 포함 GET).
    반환: {광고이름: 게시물ID} — 게시물이 하나로 정해지는 광고이름만."""
    ws = sheets_io._worksheet(config.TAB_CREATIVE_POST, config.CREATIVE_POST_COLUMNS)
    vals = ws.get_all_values()
    cached = {r[0].strip() for r in vals[1:] if r and r[0].strip()}
    new = [a for a in ads if a and a not in cached]

    rows = []
    for i in range(0, len(new), 50):
        chunk = new[i:i + 50]
        try:
            payload = request(f"{GRAPH}/{config.META_API_VERSION}/", {
                "ids": ",".join(chunk), "fields": FIELDS,
                "access_token": config.META_ACCESS_TOKEN,
            })
        except RuntimeError as e:  # 한 묶음 실패해도 수집은 계속 (다음 실행 때 재시도)
            print(f"[posts] 게시물ID 조회 실패 {len(chunk)}건 건너뜀: {e}")
            continue
        for ad_id, obj in payload.items():
            rows.append([ad_id, ads.get(ad_id, ""), post_key(obj.get("creative") or {})])
        time.sleep(2)
    if rows:
        ws.append_rows(rows, value_input_option="RAW")
    print(f"[posts] 게시물ID 캐시 {len(cached)}건 · 신규 조회 {len(rows)}/{len(new)}건")

    keys: dict[str, set] = {}
    for r in vals[1:] + rows:
        r = (list(r) + ["", "", ""])[:3]
        name, key = str(r[1]).strip(), str(r[2]).strip()
        if name and key:
            keys.setdefault(name, set()).add(key)
    return {name: next(iter(ks)) for name, ks in keys.items() if len(ks) == 1}
