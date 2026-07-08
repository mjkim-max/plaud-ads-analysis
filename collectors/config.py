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

# 구매로 인정할 action_type 우선순위 (앞에서부터 발견되는 것 사용)
PURCHASE_ACTION_TYPES = [
    "omni_purchase",
    "purchase",
    "offsite_conversion.fb_pixel_purchase",
]

# 탭 이름
TAB_META_CREATIVE_DAILY = "meta_소재일별"

META_CREATIVE_DAILY_COLUMNS = [
    "date", "campaign_name", "adset_name", "ad_id", "ad_name",
    "spend", "impressions", "clicks", "link_clicks",
    "purchases", "revenue", "ctr", "cvr", "cpa", "cpm",
]
