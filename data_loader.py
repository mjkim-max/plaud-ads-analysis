"""데이터 로딩 계층.

라이브 데이터는 비공개 Google Sheets(`meta_소재일별`·`소재매핑`)에서 읽는다.
- Cloud: st.secrets['gcp_service_account'] + st.secrets['sheet_id']
- 로컬 개발: env GOOGLE_APPLICATION_CREDENTIALS + PLAUD_SHEET_ID
"""
import json
import os
from pathlib import Path

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

DATA_DIR = Path(__file__).parent / "data"
F_GARO = DATA_DIR / "메타_캠페인_신설_생존_가로.xlsx"
F_SURV = DATA_DIR / "메타_캠페인_신설_생존분석.xlsx"

GS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
NUMERIC_COLS = ["spend", "impressions", "reach", "frequency", "clicks", "link_clicks",
                "purchase", "offline_purchase", "omni_purchase", "revenue",
                "ctr", "cvr", "cpa", "cpm"]


# 서비스계정을 담을 수 있는 secrets 섹션 이름 후보 (사용자 관례 우선)
SA_SECRET_KEYS = ("google_sheets_service_account", "gcp_service_account")


def _sa_info(val) -> dict:
    """secrets 값 → 서비스계정 dict. TOML 테이블/단일 JSON 문자열 모두 허용."""
    if isinstance(val, str):
        return json.loads(val)
    d = dict(val)
    if "type" not in d and len(d) == 1:
        only = next(iter(d.values()))
        if isinstance(only, str):
            return json.loads(only)
    return d


def _gs_client() -> gspread.Client:
    for key in SA_SECRET_KEYS:
        try:
            info = _sa_info(st.secrets[key])
        except Exception:
            continue
        creds = Credentials.from_service_account_info(info, scopes=GS_SCOPES)
        return gspread.authorize(creds)
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not path:
        raise RuntimeError("서비스계정 자격증명 없음 "
                           "(st.secrets['google_sheets_service_account'] 또는 GOOGLE_APPLICATION_CREDENTIALS).")
    creds = Credentials.from_service_account_file(path, scopes=GS_SCOPES)
    return gspread.authorize(creds)


def _sheet_id() -> str:
    for key in ("sheet_id", "SHEET_ID"):
        try:
            v = st.secrets[key]
            if isinstance(v, str) and v.strip():
                return v.strip()
        except Exception:
            continue
    sid = os.environ.get("PLAUD_SHEET_ID")
    if not sid:
        raise RuntimeError("SHEET_ID 없음 — st.secrets에 top-level `sheet_id = \"...\"` 를 추가하세요.")
    return sid


@st.cache_data(ttl=300)
def _creative_map():
    """소재매핑 → (광고이름→소재 dict, 제외 광고이름 set). 대시보드가 실시간 반영."""
    try:
        ws = _gs_client().open_by_key(_sheet_id()).worksheet("소재매핑")
        m = pd.DataFrame(ws.get_all_records())
        if m.empty:
            return {}, set()
        m["광고이름"] = m["광고이름"].astype(str).str.strip()
        m["소재"] = m["소재"].astype(str).str.strip()
        how = m["분류방식"].astype(str).str.strip() if "분류방식" in m.columns else ""
        excluded = set(m.loc[how == "제외", "광고이름"])
        shown = m[how != "제외"]
        return dict(zip(shown["광고이름"], shown["소재"])), excluded
    except Exception:
        return {}, set()


@st.cache_data(ttl=300)
def load_contract_ended() -> set:
    """소재_계약종료 탭 → 계약종료(집행 불가) 소재 이름 set. 탭 없으면 빈 set.
    열: 소재(필수) / 종료일·사유(선택). 시트에서 직접 관리하면 대시보드가 즉시 반영."""
    try:
        ws = _gs_client().open_by_key(_sheet_id()).worksheet("소재_계약종료")
        m = pd.DataFrame(ws.get_all_records())
        if m.empty or "소재" not in m.columns:
            return set()
        return {s for s in m["소재"].astype(str).str.strip() if s}
    except Exception:
        return set()


@st.cache_data(ttl=300)
def load_placement() -> pd.DataFrame:
    """meta_지면 (ad×지면 스냅샷) → 소재/포맷(이미지/영상) 조인. 탭 없으면 빈 DF."""
    try:
        ws = _gs_client().open_by_key(_sheet_id()).worksheet("meta_지면")
    except Exception:
        return pd.DataFrame()
    df = pd.DataFrame(ws.get_all_records())
    if df.empty:
        return df
    for c in ["spend", "impressions", "clicks", "link_clicks",
              "purchase", "offline_purchase", "omni_purchase", "revenue"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    for c in ["window_since", "window_until", "publisher_platform",
              "platform_position", "objective", "ad_id", "ad_name"]:
        if c in df.columns:
            df[c] = df[c].astype(str)
    soje_map, excluded = _creative_map()
    ad = df["ad_name"].str.strip()
    if excluded:
        keep = ~ad.isin(excluded)
        df, ad = df[keep], ad[keep]
    df["소재"] = ad.map(soje_map).fillna(ad) if soje_map else ad
    df["포맷"] = df["소재"].str.startswith("[이미지]").map({True: "이미지", False: "영상"})
    return df.reset_index(drop=True)


@st.cache_data(ttl=300)
def load_meta_daily() -> pd.DataFrame:
    """meta_소재일별 (라이브). 소재는 소재매핑 탭에서 실시간 조인, 제외 광고이름은 숨김."""
    ws = _gs_client().open_by_key(_sheet_id()).worksheet("meta_소재일별")
    df = pd.DataFrame(ws.get_all_records())
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in NUMERIC_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    for c in ["campaign_name", "adset_name", "objective", "ad_id", "ad_name", "소재"]:
        if c in df.columns:
            df[c] = df[c].astype(str)
    df = df.dropna(subset=["date"])

    # 소재매핑 실시간 반영: 제외 숨김 + 소재 재조인(시트가 최신 기준)
    soje_map, excluded = _creative_map()
    ad = df["ad_name"].str.strip()
    if excluded:
        keep = ~ad.isin(excluded)
        df, ad = df[keep], ad[keep]
    if soje_map:
        df["소재"] = ad.map(soje_map).fillna(df["소재"])
    return df


@st.cache_data(ttl=300)
def load_google_daily() -> pd.DataFrame:
    """google_일별 (캠페인×일자 노출·클릭·비용·채널). 없으면 빈 DF."""
    try:
        ws = _gs_client().open_by_key(_sheet_id()).worksheet("google_일별")
    except Exception:
        return pd.DataFrame()
    df = pd.DataFrame(ws.get_all_records())
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in ["impressions", "clicks", "cost"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    for c in ["campaign_name", "channel"]:
        if c in df.columns:
            df[c] = df[c].astype(str)
    return df.dropna(subset=["date"])


@st.cache_data(ttl=300)
def load_channel_sales() -> pd.DataFrame:
    """채널별 매출 (가로형·연도블록) → long df: date·channel·sales(판매 건수).
    채널 = 쿠팡·네이버·자사몰·기타. 전체 매출 행은 제외(=합계)."""
    try:
        ws = _gs_client().open_by_key(_sheet_id()).worksheet("채널별 매출")
    except Exception:
        return pd.DataFrame()
    vals = ws.get_all_values()
    channels = {"쿠팡", "네이버", "자사몰", "기타"}
    rec, year, date_cols = [], None, None
    for row in vals:
        a = row[0].strip() if row else ""
        if a.endswith("년") and a[:-1].isdigit():
            year = int(a[:-1])
            date_cols = []
            for j in range(1, len(row)):
                md = str(row[j]).strip()
                if "/" in md:
                    try:
                        mo, dy = md.split("/")
                        date_cols.append((j, int(mo), int(dy)))
                    except ValueError:
                        pass
            continue
        if a in channels and year and date_cols:
            for j, mo, dy in date_cols:
                v = str(row[j]).strip() if j < len(row) else ""
                try:
                    dt = pd.Timestamp(year=year, month=mo, day=dy)
                except ValueError:
                    continue
                rec.append({"date": dt, "channel": a, "sales": pd.to_numeric(v, errors="coerce")})
    df = pd.DataFrame(rec)
    if df.empty:
        return df
    df["sales"] = df["sales"].fillna(0)
    return df


@st.cache_data(ttl=3600)
def load_weekly_campaigns() -> pd.DataFrame:
    """주별 신설/종료/동시활성 (가로형 → 세로형 변환)."""
    raw = pd.read_excel(F_GARO, sheet_name="주별 캠페인", header=0)
    raw = raw.set_index(raw.columns[0])
    # '신설/종료/동시활성' 3개 행만, 빈 열 제거
    keep = [i for i in raw.index if str(i) in ("신설", "종료", "동시활성")]
    df = raw.loc[keep].T
    df = df[df.index.notna()]
    df.index.name = "주차"
    df = df.reset_index()
    df["주차"] = df["주차"].astype(str)
    for c in ("신설", "종료", "동시활성"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["동시활성"])


@st.cache_data(ttl=3600)
def load_cohort() -> pd.DataFrame:
    """주차별 코호트 생존율."""
    df = pd.read_excel(F_GARO, sheet_name="주차별 코호트 체류", header=0)
    df = df[df["생성 주차"].notna()]
    df = df[~df["생성 주차"].astype(str).str.startswith("※")]
    return df


@st.cache_data(ttl=3600)
def load_monthly_tiers() -> pd.DataFrame:
    """월별 단·중·장기 소재 비율."""
    df = pd.read_excel(F_GARO, sheet_name="월별 단중장기", header=0)
    df = df[df["코호트"].notna()]
    df = df[~df["코호트"].astype(str).str.startswith("※")]
    return df


@st.cache_data(ttl=3600)
def load_campaign_survival() -> pd.DataFrame:
    """캠페인별 생존기간 + CPA."""
    df = pd.read_excel(F_SURV, sheet_name="캠페인별 생존기간", header=0)
    df = df[df["캠페인"].notna()]
    df = df[~df["캠페인"].astype(str).str.startswith("※")]
    if "상태" in df.columns:
        df["상태"] = df["상태"].astype(str)
    for c in ("생존일수", "총지출(KRW)", "총구매", "CPA(KRW)"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
