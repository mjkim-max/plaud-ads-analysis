# PLAUD Ads Analysis

PLAUD 광고 성과 분석 대시보드 (Streamlit). 목표는 **자사몰 매출 우상향**이며,
광고는 **자사몰(34%)에만 귀인**한다는 원칙 위에서 분석한다.

## 로컬 실행
```bash
pip install -r requirements.txt
python3 -m streamlit run app.py
```

## 구조
```
app.py            # 대시보드 (8탭)
data_loader.py    # 데이터 로딩 계층 (지금은 로컬 엑셀 → Phase 2에서 API/BigQuery로 교체)
data/             # 캠페인 신설·생존 엑셀 (private repo 내 보관)
.streamlit/
  config.toml     # 테마
  secrets.toml    # 시크릿 (git 제외 · Community Cloud는 Secrets UI 사용)
```

## 로드맵
- **Phase 1 (현재)**: 로컬 엑셀 기반 MVP — 개요 / 캠페인 병렬 / 캠페인 생존 / 전략 탭.
- **Phase 2**: Meta(인증됨)·Google Ads·자사몰/네이버/쿠팡 매출 API → BigQuery 적재 → 실시간화.
  소재 생존·메타 효율·채널별·소재 품질 탭 채우기.
- **Phase 3**: 일 단위 자동 수집 → 대시보드 자동 최신화 (+ 아침 요약).

## 보안
- API 토큰·시크릿은 **절대 커밋 금지** (`.gitignore` 처리). Community Cloud는 앱 Secrets UI에 등록.
- repo는 **Private** 유지.

## 근거 분석 문서 (Fitten vault)
`광고분석_종합정리.md` · `광고분석_대시보드_가이드.md` · `광고분석_대시보드_가이드_보강분.md`
