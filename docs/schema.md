# 데이터 워크북 스키마 (Google Sheets 중심)

광고 데이터의 **단일 진실 소스 = 비공개 Google Sheets 워크북 1개**.
탭별로 grain을 나눠 쌓고, Streamlit 앱은 `data_loader`로 읽는다. repo(public)엔 데이터를 두지 않는다.

## 워크북 탭 구성

| 탭 이름 | grain | 채우는 주체 | 비고 |
|---|---|---|---|
| `meta_소재일별` | 소재(ad) × 일자 (지출>0) | Meta 수집기(자동) | 대시보드 핵심. 2025 ~7천행 / 2026 ~1.4만행 |
| `google_일별` | 캠페인/채널 × 일자 | Google 수집기(자동, 예정) | 검색·PMax·디멘드젠·GDN |
| `sales_일별` | 일자 × 채널(자사몰·네이버·쿠팡) | **수기 입력(기존)** | 이미 관리 중인 시트 연결 |

## `meta_소재일별` 컬럼 (수집기가 기록)

| 컬럼 | 의미 | 출처 |
|---|---|---|
| `date` | 일자 (YYYY-MM-DD) | insights date_start |
| `campaign_name` | 캠페인명 | campaign_name |
| `adset_name` | 광고세트명 | adset_name |
| `objective` | 캠페인 목표 (필터·검증용) | objective |
| `ad_id` | 소재 고유 ID (업서트 키) | ad_id |
| `ad_name` | 소재명 (기존 "I열 소재명") | ad_name |
| `spend` | 지출(KRW) | spend |
| `impressions` | 노출 | impressions |
| `clicks` | 클릭 | clicks |
| `link_clicks` | 링크클릭 | inline_link_clicks |
| `purchase` | 웹(픽셀) 구매 | offsite_conversion.fb_pixel_purchase |
| `offline_purchase` | 오프라인 구매 | offline_conversion.purchase |
| `omni_purchase` | 전체(옴니) 구매 | omni_purchase |
| `revenue` | 구매금액(KRW, 전체) | action_values(omni) — ROAS용 |
| `ctr` | 클릭÷노출 | 파생 |
| `cvr` | 전체구매÷클릭 | 파생 |
| `cpa` | 지출÷전체구매 | 파생 |
| `cpm` | 지출÷노출×1000 | 파생 |

- **업서트 키 = (date, ad_id)**. 수집기는 매 실행마다 최근 N일치를 다시 당겨(늦게 붙는 전환 보정) 해당 일자 행을 교체한다.
- **구매목표 필터**: 캠페인 `objective`가 `OUTCOME_SALES`/`CONVERSIONS`/`PRODUCT_CATALOG_SALES` 인 것만 적재. 트래픽·인지 등 비구매 목표 광고는 제외.
- **행 필터**: `지출>0` 또는 `구매>0` 이면 유지. (지출0·구매0 행만 버림)
- `revenue`는 지금 대시보드엔 안 쓰지만 **ROAS 분석(열린 과제)** 위해 미리 쌓아둔다.

## 보안
- 워크북은 **비공개**. 편집 권한은 본인 + 수집기용 **서비스계정** 이메일만.
- 자격증명(Meta 토큰·서비스계정 JSON·SHEET_ID)은 **절대 repo에 두지 않음** → GitHub Actions Secrets + Streamlit Secrets.
