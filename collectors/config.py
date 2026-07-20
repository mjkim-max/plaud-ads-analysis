"""수집기 공통 설정. 민감값은 전부 환경변수에서 읽는다 (repo에 하드코딩 금지)."""
import os

# ── Google Sheets ──
SHEET_ID = os.environ.get("PLAUD_SHEET_ID", "")
# 서비스계정 JSON: 문자열(GOOGLE_SERVICE_ACCOUNT_JSON) 또는 파일경로(GOOGLE_APPLICATION_CREDENTIALS)
GOOGLE_SA_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_SA_FILE = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

# ── Meta Marketing API ──
META_API_VERSION = os.environ.get("META_API_VERSION", "v21.0")
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
# 'act_XXXXXXXXXX' 형식. act_ 접두어 없으면 자동으로 붙인다.
_acc = os.environ.get("META_AD_ACCOUNT_ID", "")
META_AD_ACCOUNT_ID = _acc if _acc.startswith("act_") or not _acc else f"act_{_acc}"

# 최근 며칠을 매 실행마다 다시 당겨 덮어쓸지 (늦게 붙는 전환 보정)
LOOKBACK_DAYS = int(os.environ.get("META_LOOKBACK_DAYS", "30"))

# 백필용 명시적 날짜 범위 (비우면 LOOKBACK_DAYS 사용)
META_SINCE = os.environ.get("META_SINCE", "").strip()
META_UNTIL = os.environ.get("META_UNTIL", "").strip()

# 구매 카테고리별 action_type 후보 (카테고리 안에서 앞에서부터 첫 매칭 1개만 사용)
PURCHASE_TYPES = {
    "purchase":         ["offsite_conversion.fb_pixel_purchase", "web_in_store_purchase", "purchase"],  # 웹(픽셀) 구매
    "offline_purchase": ["offline_conversion.purchase"],                                                 # 오프라인 구매
    "omni_purchase":    ["omni_purchase"],                                                               # 전체(옴니) 구매
}
# 구매금액(매출) — 전체 기준
REVENUE_TYPES = ["omni_purchase", "offsite_conversion.fb_pixel_purchase", "purchase"]

# 구매목표로 인정할 캠페인 objective (판매/전환 계열만; 트래픽·인지 등은 제외)
PURCHASE_OBJECTIVES = {"OUTCOME_SALES", "CONVERSIONS", "PRODUCT_CATALOG_SALES"}

# ── Google Ads API ──
GADS_API_VERSION = os.environ.get("GOOGLE_ADS_API_VERSION", "v21")
GADS_DEVELOPER_TOKEN = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", "")
GADS_CLIENT_ID = os.environ.get("GOOGLE_ADS_CLIENT_ID", "")
GADS_CLIENT_SECRET = os.environ.get("GOOGLE_ADS_CLIENT_SECRET", "")
GADS_REFRESH_TOKEN = os.environ.get("GOOGLE_ADS_REFRESH_TOKEN", "")
GADS_LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "").strip()
GADS_CUSTOMER_ID = os.environ.get("GOOGLE_ADS_CUSTOMER_ID", "").replace("-", "").strip()

# 탭 이름
TAB_META_CREATIVE_DAILY = "meta_소재일별"
TAB_CREATIVE_MAP = "소재매핑"
TAB_GOOGLE_DAILY = "google_일별"
GOOGLE_DAILY_COLUMNS = ["date", "campaign_name", "channel", "impressions", "clicks", "cost"]

META_CREATIVE_DAILY_COLUMNS = [
    "date", "campaign_name", "adset_name", "objective", "ad_id", "ad_name", "소재",
    "spend", "impressions", "reach", "frequency", "clicks", "link_clicks",
    "purchase", "offline_purchase", "omni_purchase", "revenue",
    "ctr", "cvr", "cpa", "cpm",
]

# 소재매핑 탭: 광고이름 → 소재(정규명) + 분류방식(수동/자동)
CREATIVE_MAP_COLUMNS = ["광고이름", "소재", "분류방식"]

# 지면(placement) 스냅샷 — publisher_platform × platform_position 별 집계.
# 매 실행마다 최근 N일 윈도로 덮어씀(스냅샷). 포맷(이미지/영상)별 지면 CPM 검증용.
TAB_META_PLACEMENT = "meta_지면"
PLACEMENT_WINDOW_DAYS = int(os.environ.get("META_PLACEMENT_DAYS", "30"))
META_PLACEMENT_COLUMNS = [
    "window_since", "window_until", "publisher_platform", "platform_position",
    "objective", "ad_id", "ad_name",
    "spend", "impressions", "clicks", "link_clicks",
    "purchase", "offline_purchase", "omni_purchase", "revenue",
]

# 성별×연령(age × gender) 스냅샷 — 최근 N일 윈도로 덮어씀.
TAB_META_GENDER = "meta_성별"
GENDER_WINDOW_DAYS = int(os.environ.get("META_GENDER_DAYS", "30"))
META_GENDER_COLUMNS = [
    "window_since", "window_until", "age", "gender",
    "objective", "ad_id", "ad_name",
    "spend", "impressions", "clicks", "link_clicks",
    "purchase", "offline_purchase", "omni_purchase", "revenue",
]
