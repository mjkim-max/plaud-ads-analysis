"""광고이름 → 소재(정규명) 매핑.

- 수동 매핑(소재매핑 탭)이 우선. 없는 광고이름은 normalize() 규칙으로 자동 분류하고
  분류방식='자동'으로 매핑 탭에 등록해 사람이 나중에 검토·수정할 수 있게 한다.
- 정규화 규칙 재현율: 기존 수동 매핑 대비 약 94%. (나머지는 옛 네이밍·의미통합이라 수동 표가 담당)
"""
import re

from collectors import config, sheets_io


def normalize(ad_name: str) -> str:
    """광고이름에서 소재(정규명)를 추정.
    날짜_·계정코드_·'마이너_' 접두 제거 + '- 사본' 제거 + 공백·언더스코어 제거.
    """
    s = str(ad_name).strip()
    s = re.sub(r"^\d{5,8}_", "", s)        # 날짜_ (오타 포함 5~8자리)
    s = re.sub(r"^[A-Z]{2,3}_", "", s)     # 계정코드_ (PP/PL/NP...)
    s = re.sub(r"^마이너_", "", s)         # '마이너' 그룹 라벨
    s = re.sub(r"\s*-\s*사본", "", s)      # ' - 사본' 반복
    s = s.replace("_", "").replace(" ", "").strip()
    return s or str(ad_name).strip()


def load_map() -> dict:
    """소재매핑 탭을 {광고이름: 소재} 로 로드."""
    df = sheets_io.read_tab(config.TAB_CREATIVE_MAP, config.CREATIVE_MAP_COLUMNS)
    m = {}
    for _, r in df.iterrows():
        ad = str(r.get("광고이름", "")).strip()
        so = str(r.get("소재", "")).strip()
        if ad and so:
            m[ad] = so
    return m


def assign(ad_names, existing: dict):
    """각 광고이름 → 소재. 매핑에 없으면 normalize로 자동분류.
    반환: (소재 리스트, 신규 등록행 리스트[분류방식='자동'])."""
    resolved, new_rows, seen_new = [], [], set()
    for ad in ad_names:
        ad = str(ad).strip()
        if ad in existing:
            resolved.append(existing[ad])
        else:
            so = normalize(ad)
            resolved.append(so)
            if ad not in seen_new:
                new_rows.append({"광고이름": ad, "소재": so, "분류방식": "자동"})
                seen_new.add(ad)
    return resolved, new_rows
