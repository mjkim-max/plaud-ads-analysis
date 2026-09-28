"""소재매핑 자동분류 백테스트.

소재매핑 탭의 수동·자동 행(=사람이 넣었거나 검수한 정답)을 정답지로,
구 normalize() 와 신 smart_guess() 의 재현율을 비교한다.
매핑 자체는 건드리지 않는 읽기 전용 스크립트.

실행: PLAUD_SHEET_ID=... GOOGLE_SERVICE_ACCOUNT_JSON=... python -m collectors.backtest_mapping
"""
from collectors import config, creative_mapping, sheets_io
from collectors.creative_mapping import _build_known, _norm, normalize, smart_guess


def main() -> None:
    df = sheets_io.read_tab(config.TAB_CREATIVE_MAP, config.CREATIVE_MAP_COLUMNS)
    rows = []
    for _, r in df.iterrows():
        ad = str(r.get("광고이름", "")).strip()
        so = str(r.get("소재", "")).strip()
        how = str(r.get("분류방식", "")).strip()
        if ad and so and how in ("수동", "자동"):
            rows.append((ad, so, how))
    known = _build_known(so for _, so, _h in rows)
    print(f"정답 행: {len(rows)} (수동 {sum(1 for r in rows if r[2]=='수동')} · "
          f"자동 {sum(1 for r in rows if r[2]=='자동')}) · distinct 소재 {len(known)}")

    old_ok = new_ok = 0
    miss_new = []
    for ad, so, how in rows:
        t = _norm(so)
        if _norm(normalize(ad)) == t:
            old_ok += 1
        pred, matched = smart_guess(ad, known)
        if _norm(pred) == t:
            new_ok += 1
        else:
            miss_new.append((how, ad, so, pred, matched))

    n = len(rows)
    print(f"구 normalize : {old_ok}/{n} = {old_ok/n*100:.1f}%")
    print(f"신 smart_guess: {new_ok}/{n} = {new_ok/n*100:.1f}%")
    print(f"\n신규 로직 불일치 {len(miss_new)}건 (최대 40건 표시):")
    for how, ad, so, pred, matched in miss_new[:40]:
        tag = "대조" if matched else "파싱"
        print(f"  [{how}/{tag}] {ad!r} → 예측 {pred!r} / 정답 {so!r}")


if __name__ == "__main__":
    main()
