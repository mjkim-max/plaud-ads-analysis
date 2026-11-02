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


_EXACT = "\x00"  # 접두어 뗀 키 표시 — 부분일치 금지, 전체일치만


def _build_known(sojs) -> dict:
    """소재명 목록 → {_norm(소재): 소재} 대조 사전.
    '[이미지] 금붕어' 처럼 포맷 접두어가 붙은 소재는 접두어 뗀 키도 추가해
    광고이름 '금붕어'가 원래 소재로 매핑되게 한다. (접두어 없는 원형이 항상 우선)
    접두어 뗀 키는 전체일치만 허용 ('뎁프로2'가 '[이미지] 프로'로 붙는 것 방지).
    '이름1' 소재는 숫자 뗀 키도 추가 — 숫자 없는 이름 = 1."""
    known, stripped, base1 = {}, {}, {}
    for so in sojs:
        so = str(so).strip()
        if not so:
            continue
        known.setdefault(_norm(so), so)
        bare = _PREFIX_TAG.sub("", so).strip()
        if bare and bare != so:
            stripped.setdefault(_EXACT + _norm(bare), so)
        m = re.match(r"^(.+?)1(\s*\((?:PP|NP|PL)\))?$", so)
        if m and not _PREFIX_TAG.match(so):
            base1.setdefault(_norm(m.group(1) + (m.group(2) or "")), so)
    for d in (stripped, base1):
        for k, v in d.items():
            known.setdefault(k, v)
    return known


def _match_known(text_norm: str, tokset: set, known: dict) -> str:
    """가장 긴 매칭 소재를 반환. 한 글자 소재는 토큰 일치일 때만.
    뒤에 숫자가 이어지는 부분일치는 버린다 ('뎁프로'가 '뎁프로2'에 붙는 것 방지)."""
    best = ""
    for k in known:
        if k.startswith(_EXACT):
            if k[1:] == text_norm and len(k) - 1 > len(best.lstrip(_EXACT)):
                best = k
        elif len(k) >= 2:
            if len(k) > len(best) and re.search(re.escape(k) + r"(?!\d)", text_norm):
                best = k
        elif k in tokset and len(k) > len(best):
            best = k
    return best


def smart_guess(ad_name: str, known: dict | None = None):
    """광고이름 → (소재 추정, 기존소재 매칭 여부).
    known: {_norm(소재): 소재} — 기존에 등록된 소재명 사전.
    """
    s = _strip(ad_name)
    # 버전 표기: '(기획)'·'_기획' → 2, '(기존)' → 1  ('뎁프로(기획)' → '뎁프로2')
    s = re.sub(r"\(기존\)", "1", re.sub(r"[_\s]*\(?기획\)?", "2", s))
    toks = [t for t in re.split(r"[_\s]+", s) if t]

    # 구조 토큰(날짜·계정코드·타겟 라벨) 제거한 핵심 토큰
    core = []
    for i, t in enumerate(toks):
        if i == 0 and _DATE_TOK.match(t):
            continue
        if i <= 2 and _ACCT_TOK.match(t):
            continue
        if _STRUCT_TOK.match(t):
            continue
        core.append(t)

    # ① 기존 소재명 대조 — 핵심 토큰 문자열 우선, 없으면 원문 전체로 재시도
    #   ('리타게팅_0원'에서 구조 토큰 '리타게팅'이 소재로 오매칭되는 것 방지)
    if known:
        for text, tokens in ((("".join(core)), core), (s, toks)):
            best = _match_known(_norm(text), {_norm(t) for t in tokens}, known)
            if best:
                return known[best], True

    # ② 파싱 폴백 — 핵심 토큰 잔여를 소재명으로 제안
    guess = "".join(core).strip()
    return (guess or s), False


# 버전 표기: (기존) → 1, (기획) → 2. 계정 접미어 (PP)/(NP)/(PL)은 유지
_VER = re.compile(r"^(.*?)\s*\((기존|기획)\)\s*(\((?:PP|NP|PL)\))?$")
_ACCT_IN_AD = re.compile(r"(?:^|_)(PP|NP|PL)(?:_|$)")


def canon(so: str, known: dict) -> str:
    """추정 소재명 → 표준 소재명.
    ① '(기존)'→'1', '(기획)'→'2'
    ② 공백·괄호만 다른 기존 소재가 있으면 그 이름 ('릴쏸(PP)' → '릴쏸 (PP)')
    ③ 숫자 없는 이름인데 '이름1' 소재가 있으면 '이름1' (숫자 없는 것 = 1)"""
    m = _VER.match(so)
    if m:
        so = f"{m.group(1)}{'1' if m.group(2) == '기존' else '2'}" + (f" {m.group(3)}" if m.group(3) else "")
    for k in (_norm(so), _EXACT + _norm(so), _norm(so + "1")):
        if k in known:
            return known[k]
    return so


def by_post(ad_name: str, post_of: dict, post_so: dict) -> str:
    """광고의 게시물 ID가 확인(O)된 소재 하나에만 걸려 있으면 그 소재. 아니면 ''.
    여러 소재에 걸리면 광고이름의 계정(PP/NP/PL)과 접미어가 맞는 소재로 좁힌다."""
    cands = post_so.get(post_of.get(ad_name, ""), set())
    if len(cands) > 1:
        m = _ACCT_IN_AD.search(ad_name)
        if m:
            cands = {s for s in cands if s.endswith(f"({m.group(1)})")}
    return next(iter(cands)) if len(cands) == 1 else ""


def load_post_so(post_of: dict) -> dict:
    """소재매핑의 확인(O) 행 → {게시물ID: {소재}}."""
    df = sheets_io.read_tab(config.TAB_CREATIVE_MAP, config.CREATIVE_MAP_COLUMNS)
    out: dict[str, set] = {}
    if "확인" not in df.columns:
        return out
    for _, r in df.iterrows():
        ad, so = str(r.get("광고이름", "")).strip(), str(r.get("소재", "")).strip()
        key = post_of.get(ad)
        if key and so and str(r.get("확인", "")).strip().upper() == "O" \
                and str(r.get("분류방식", "")).strip() != "제외":
            out.setdefault(key, set()).add(so)
    return out


def load_map() -> dict:
    """소재매핑 탭을 {광고이름: 소재} 로 로드."""
    m, _ = load_map_and_known()
    return m


def load_map_and_known():
    """소재매핑 탭 → ({광고이름: 소재}, {_norm(소재): 소재}).
    known 사전에는 분류방식='제외' 행의 소재(정크명)는 넣지 않는다."""
    df = sheets_io.read_tab(config.TAB_CREATIVE_MAP, config.CREATIVE_MAP_COLUMNS)
    m, sojs = {}, []
    for _, r in df.iterrows():
        ad = str(r.get("광고이름", "")).strip()
        so = str(r.get("소재", "")).strip()
        how = str(r.get("분류방식", "")).strip()
        if ad and so:
            m[ad] = so
            if how != "제외":
                sojs.append(so)
    return m, _build_known(sojs)


REVIEW_HEADERS = ["확인", "확인필요"]  # 소재매핑 D·E열


def sync_review() -> tuple[int, int]:
    """소재매핑 D(확인)·E(확인필요) 열 정리.
    - D: 사람이 확인한 행은 'O'. 수동 행은 기본 'O'. 자동 행은 같은 소재명에 'O'가 있으면 'O'.
      이미 들어 있는 D 값은 건드리지 않는다.
    - E: 자동 행에만 수식 — 같은 소재명에 'O'가 하나라도 있으면 공란, 없으면 '확인필요'.
      (D에 O를 치는 즉시 시트에서 바로 사라지게 수식으로 둔다)
    반환: (자동 O 새로 표시한 행 수, 확인필요 행 수)."""
    ws = sheets_io._worksheet(config.TAB_CREATIVE_MAP, config.CREATIVE_MAP_COLUMNS)
    vals = ws.get_all_values()
    rows = [(r + [""] * 5)[:5] for r in vals[1:]]
    for r in rows:
        if r[0].strip() and not r[3].strip() and r[2].strip() == "수동":
            r[3] = "O"
    ok = {r[1].strip() for r in rows if r[3].strip().upper() == "O"}
    n_auto_o = n_need = 0
    for i, r in enumerate(rows, start=2):
        auto = r[0].strip() and r[2].strip() == "자동"
        if auto and not r[3].strip() and r[1].strip() in ok:
            r[3] = "O"
            n_auto_o += 1
        r[4] = f'=IF(COUNTIFS($B:$B,B{i},$D:$D,"O"),"","확인필요")' if auto else ""
        if auto and r[1].strip() not in ok:
            n_need += 1
    out = [REVIEW_HEADERS] + [[r[3], r[4]] for r in rows]
    # 키워드 인자 — gspread 5(range, values)·6(values, range) 위치 순서가 반대
    ws.update(range_name=f"D1:E{len(out)}", values=out, value_input_option="USER_ENTERED")
    return n_auto_o, n_need


def assign(ad_names, existing: dict, known: dict | None = None,
           post_of: dict | None = None, post_so: dict | None = None):
    """각 광고이름 → 소재. 매핑에 없으면 자동분류:
    ① 같은 게시물 ID의 확인(O) 소재 (by_post) → 없으면 ② smart_guess + canon.
    반환: (소재 리스트, 신규 등록행 리스트[분류방식='자동']).
    known 이 None 이면 existing 의 소재값들로 사전을 만든다."""
    if known is None:
        known = _build_known(existing.values())
    resolved, new_rows, seen_new = [], [], set()
    for ad in ad_names:
        ad = str(ad).strip()
        if ad in existing:
            resolved.append(existing[ad])
        else:
            so = by_post(ad, post_of or {}, post_so or {})
            if not so:
                so = canon(smart_guess(ad, known)[0], known)
            resolved.append(so)
            if ad not in seen_new:
                new_rows.append({"광고이름": ad, "소재": so, "분류방식": "자동"})
                seen_new.add(ad)
                known.setdefault(_norm(so), so)  # 같은 배치 내 후속 광고도 이 소재로 묶이게
    return resolved, new_rows
