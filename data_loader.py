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
NUMERIC_COLS = ["spend", "impressions", "clicks", "link_clicks",
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


@st.cache_data(ttl=1800)
def load_meta_daily() -> pd.DataFrame:
    """meta_소재일별 (라이브). 소재 단위 분석의 원천."""
    ws = _gs_client().open_by_key(_sheet_id()).worksheet("meta_소재일별")
    df = pd.DataFrame(ws.get_all_records())
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for c in NUMERIC_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    # 문자열 컬럼 강제 str (gspread 숫자 자동변환 → Arrow 혼합타입 방지)
    for c in ["campaign_name", "adset_name", "objective", "ad_id", "ad_name", "소재"]:
        if c in df.columns:
            df[c] = df[c].astype(str)
    return df.dropna(subset=["date"])


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
