"""광고이름 → 소재(정규명) 매핑.

- 수동 매핑(소재매핑 탭)이 우선. 없는 광고이름은 smart_guess() 로 자동 분류하고
  분류방식='자동'으로 매핑 탭에 등록해 사람이 나중에 검토·수정할 수 있게 한다.
- smart_guess 2단계:
  ① 기존 소재명 대조 — 광고이름 안에 이미 등록된 소재명이 들어 있으면 그 소재로 매핑
    (재집행·이관·타겟변형 광고는 거의 전부 여기서 잡힘)
  ② 토큰 파싱 — 날짜·계정코드·타겟 구조 토큰(유사/신규N/저·고/관심사 등)을 걷어내고
    남는 것을 소재명으로 제안
- normalize() 는 구(舊) 단순 규칙 — reclassify/remap 스크립트 호환용으로 유지.
"""
from __future__ import annotations

import re

from collectors import config, sheets_io


def normalize(ad_name: str) -> str:
    """(구버전) 광고이름에서 소재(정규명)를 추정.
    날짜_·계정코드_·'마이너_' 접두 제거 + '- 사본' 제거 + 공백·언더스코어 제거.
    """
    s = str(ad_name).strip()
    s = re.sub(r"^\d{5,8}_", "", s)        # 날짜_ (오타 포함 5~8자리)
    s = re.sub(r"^[A-Z]{2,3}_", "", s)     # 계정코드_ (PP/PL/NP...)
    s = re.sub(r"^마이너_", "", s)         # '마이너' 그룹 라벨
    s = re.sub(r"\s*-\s*사본", "", s)      # ' - 사본' 반복
    s = s.replace("_", "").replace(" ", "").strip()
    return s or str(ad_name).strip()


# ── smart_guess ──────────────────────────────────────────────
_PREFIX_TAG = re.compile(r"^\s*\[[^\]]+\]\s*")          # [TEST] [LOW] [RETRY] ...
_COPY_SUFFIX = re.compile(r"\s*-\s*사본")
_DATE_TOK = re.compile(r"^\d{5,8}$")
_ACCT_TOK = re.compile(r"^(?:PP|PL|NP|MNL|ASC)$")
# 타겟·캠페인 구조 토큰 (소재명이 아닌 것)
_STRUCT_TOK = re.compile(
    r"^(?:유사(?:타겟)?\d*|유사제외(?:테스트)?\d*(?:\(.+\))?|신규\d*|짬통(?:테스트)?\d*(?:\(.+\))?|"
    r"저|고|남|여|저연령|고연령|관심사|기존|마이너\d*|리타게팅(?:\(.+\))?|"
    r"ABO|CBO|테스트\d*|\d{4}(?:남|여)?)$"
)


def _norm(s: str) -> str:
    """비교용 정규형: 공백·언더스코어·괄호 제거 + 소문자.
    (괄호 제거로 '지연이네(기획)' ↔ '지연이네_기획' 표기 차이를 흡수)"""
    return re.sub(r"[\s_()\[\]]+", "", str(s)).lower()


def _strip(ad_name: str) -> str:
    s = _PREFIX_TAG.sub("", str(ad_name).strip())
    return _COPY_SUFFIX.sub("", s).strip()


def smart_guess(ad_name: str, known: dict | None = None):
    """광고이름 → (소재 추정, 기존소재 매칭 여부).
    known: {_norm(소재): 소재} — 기존에 등록된 소재명 사전.
    """
    s = _strip(ad_name)
    toks = [t for t in re.split(r"[_\s]+", s) if t]
    full = _norm(s)

    # ① 기존 소재명 대조 — 가장 긴 매칭 우선. 한 글자 소재는 토큰 일치일 때만.
    if known:
        tokset = {_norm(t) for t in toks}
        best = ""
        for k in known:
            if len(k) >= 2:
                if k in full and len(k) > len(best):
                    best = k
            elif k in tokset and len(k) > len(best):
                best = k
        if best:
            return known[best], True

    # ② 토큰 파싱 — 구조 토큰 제거 후 잔여를 소재명으로
    core = []
    for i, t in enumerate(toks):
        if i == 0 and _DATE_TOK.match(t):
            continue
        if i <= 2 and _ACCT_TOK.match(t):
            continue
        if _STRUCT_TOK.match(t):
            continue
        core.append(t)
    guess = "".join(core).strip()
    return (guess or s), False


def load_map() -> dict:
    """소재매핑 탭을 {광고이름: 소재} 로 로드."""
    m, _ = load_map_and_known()
    return m


def load_map_and_known():
    """소재매핑 탭 → ({광고이름: 소재}, {_norm(소재): 소재}).
    known 사전에는 분류방식='제외' 행의 소재(정크명)는 넣지 않는다."""
    df = sheets_io.read_tab(config.TAB_CREATIVE_MAP, config.CREATIVE_MAP_COLUMNS)
    m, known = {}, {}
    for _, r in df.iterrows():
        ad = str(r.get("광고이름", "")).strip()
        so = str(r.get("소재", "")).strip()
        how = str(r.get("분류방식", "")).strip()
        if ad and so:
            m[ad] = so
            if how != "제외":
                known.setdefault(_norm(so), so)
    return m, known


def assign(ad_names, existing: dict, known: dict | None = None):
    """각 광고이름 → 소재. 매핑에 없으면 smart_guess 로 자동분류.
    반환: (소재 리스트, 신규 등록행 리스트[분류방식='자동']).
    known 이 None 이면 existing 의 소재값들로 사전을 만든다."""
    if known is None:
        known = {}
        for so in existing.values():
            if so:
                known.setdefault(_norm(so), so)
    resolved, new_rows, seen_new = [], [], set()
    for ad in ad_names:
        ad = str(ad).strip()
        if ad in existing:
            resolved.append(existing[ad])
        else:
            so, _matched = smart_guess(ad, known)
            resolved.append(so)
            if ad not in seen_new:
                new_rows.append({"광고이름": ad, "소재": so, "분류방식": "자동"})
                seen_new.add(ad)
                known.setdefault(_norm(so), so)  # 같은 배치 내 후속 광고도 이 소재로 묶이게
    return resolved, new_rows
