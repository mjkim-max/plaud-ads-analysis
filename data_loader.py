"""데이터 로딩 계층.

지금은 로컬 엑셀(data/*.xlsx)에서 읽는다. Phase 2 에서 이 함수들의 내부만
Meta/Google/매출 API → BigQuery 조회로 교체하면 앱(app.py)은 안 건드려도 된다.
"""
from pathlib import Path
import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).parent / "data"
F_GARO = DATA_DIR / "메타_캠페인_신설_생존_가로.xlsx"
F_SURV = DATA_DIR / "메타_캠페인_신설_생존분석.xlsx"


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
