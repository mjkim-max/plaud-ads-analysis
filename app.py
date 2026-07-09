"""PLAUD 광고 성과 대시보드 — 라이브 Google Sheets 기반.

소재(정규명) 단위 지표를 그래프로 보여주는 데 집중. 판단 라벨은 두지 않는다.
데이터: meta_소재일별(매일 자동수집) + 소재매핑(광고이름→소재, 실시간).
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import data_loader as dl

st.set_page_config(page_title="PLAUD 광고 대시보드", page_icon="📊", layout="wide")
BLUE, GREEN, AMBER, RED, GRAY = "#2563eb", "#22c55e", "#f59e0b", "#ef4444", "#9ca3af"
LIVE_DAYS = 14

try:
    df = dl.load_meta_daily()
except Exception as e:
    st.error(f"데이터 로드 실패: {e}")
    st.stop()
if df.empty:
    st.warning("데이터가 비어있습니다.")
    st.stop()

max_date = df["date"].max()
st.sidebar.header("필터")
dmin, dmax = df["date"].min().date(), max_date.date()
rng = st.sidebar.date_input("기간", (dmin, dmax), min_value=dmin, max_value=dmax)
if isinstance(rng, tuple) and len(rng) == 2:
    df = df[(df["date"].dt.date >= rng[0]) & (df["date"].dt.date <= rng[1])]
st.sidebar.caption(f"소재 {df['소재'].nunique()}개 · 광고 {df['ad_name'].nunique()}개 · {len(df):,}행")
st.sidebar.caption(f"최신: {max_date.date()}")


@st.cache_data(ttl=300)
def creative_summary(d: pd.DataFrame) -> pd.DataFrame:
    spent = d[d["spend"] > 0].groupby("소재")["date"]
    g = d.groupby("소재")
    s = pd.DataFrame({
        "지출": g["spend"].sum(), "노출": g["impressions"].sum(), "클릭": g["clicks"].sum(),
        "구매_웹": g["purchase"].sum(), "구매_오프": g["offline_purchase"].sum(),
        "구매_전체": g["omni_purchase"].sum(), "광고수": g["ad_id"].nunique(),
        "캠페인수": g["campaign_name"].nunique(),
        "최초집행": spent.min(), "최종집행": spent.max(), "활성일수": spent.nunique(),
    })
    s["수명일"] = (s["최종집행"] - s["최초집행"]).dt.days + 1
    s["CPA"] = (s["지출"] / s["구매_전체"]).where(s["구매_전체"] > 0)
    s["CTR"] = (s["클릭"] / s["노출"] * 100).where(s["노출"] > 0)
    s["CVR"] = (s["구매_전체"] / s["클릭"] * 100).where(s["클릭"] > 0)
    return s.reset_index()


def resample_metrics(d: pd.DataFrame, freq: str) -> pd.DataFrame:
    t = d.set_index("date").resample(freq).agg(
        지출=("spend", "sum"), 노출=("impressions", "sum"),
        클릭=("clicks", "sum"), 구매=("omni_purchase", "sum")).reset_index()
    t = t[t["지출"] > 0]
    t["CPA"] = (t["지출"] / t["구매"]).where(t["구매"] > 0)
    t["CTR"] = (t["클릭"] / t["노출"] * 100).where(t["노출"] > 0)
    t["CVR"] = (t["구매"] / t["클릭"] * 100).where(t["클릭"] > 0)
    t["CPM"] = (t["지출"] / t["노출"] * 1000).where(t["노출"] > 0)
    return t


def spend_cpa_chart(t, title, key):
    f = go.Figure()
    f.add_bar(x=t["date"], y=t["지출"], name="지출", marker_color="#bfdbfe")
    f.add_scatter(x=t["date"], y=t["CPA"], name="CPA", mode="lines+markers",
                  line=dict(color=RED, width=3), yaxis="y2")
    f.update_layout(height=320, margin=dict(t=44, b=10), yaxis=dict(title="지출"),
                    yaxis2=dict(title="CPA", overlaying="y", side="right"),
                    legend=dict(orientation="h", y=1.14, x=0))
    st.markdown(f"**{title}**")
    st.plotly_chart(f, use_container_width=True, key=key)


def ctr_cvr_chart(t, title, key):
    f = go.Figure()
    f.add_scatter(x=t["date"], y=t["CTR"], name="CTR%", mode="lines+markers", line=dict(color=BLUE))
    f.add_scatter(x=t["date"], y=t["CVR"], name="CVR%", mode="lines+markers", line=dict(color=GREEN))
    f.update_layout(height=320, margin=dict(t=44, b=10), yaxis_title="%",
                    legend=dict(orientation="h", y=1.14, x=0))
    st.markdown(f"**{title}**")
    st.plotly_chart(f, use_container_width=True, key=key)


cs = creative_summary(df)

st.title("📊 PLAUD 광고 성과 대시보드")
st.caption(f"소재 단위 지표 · 데이터 {dmin} ~ {dmax} (매일 자동 갱신)")

tabs = st.tabs(["① 개요", "② 월별 소재 컨디션", "③ 제작월별 진단", "④ 메타 효율 추이", "⑤ 소재 생존·품질"])

# ─────────────────────────── ① 개요 ───────────────────────────
with tabs[0]:
    tot_spend, tot_omni = df["spend"].sum(), df["omni_purchase"].sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("총 지출", f"₩{tot_spend/1e8:.2f}억")
    c2.metric("총 구매(전체)", f"{int(tot_omni):,}건")
    c3.metric("통합 CPA", f"₩{tot_spend/tot_omni:,.0f}" if tot_omni else "-")
    c4.metric("소재 수", f"{cs['소재'].nunique()}개")
    st.subheader("월별 지출 vs 구매")
    m = resample_metrics(df, "MS")
    fig = go.Figure()
    fig.add_bar(x=m["date"], y=m["지출"], name="지출", marker_color=BLUE)
    fig.add_scatter(x=m["date"], y=m["구매"], name="구매", mode="lines+markers",
                    line=dict(color=GREEN, width=3), yaxis="y2")
    fig.update_layout(height=360, margin=dict(t=30, b=10), yaxis=dict(title="지출"),
                      yaxis2=dict(title="구매", overlaying="y", side="right"),
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────── ② 월별 소재 컨디션 ───────────────────────────
with tabs[1]:
    st.subheader("월별 소재 컨디션")
    st.caption(f"제작월별 만든 소재 수 · 현재 LIVE 수 · 평균수명 · 성과 합계. (LIVE = 최근 {LIVE_DAYS}일 내 집행)")
    csm = cs.copy()
    csm["제작월"] = csm["최초집행"].dt.to_period("M").astype(str)
    live = csm["최종집행"] >= (max_date - pd.Timedelta(days=LIVE_DAYS))
    summ = csm.groupby("제작월").agg(
        제작소재수량=("소재", "nunique"), 지출=("지출", "sum"), 노출=("노출", "sum"),
        클릭=("클릭", "sum"), 전환=("구매_전체", "sum"), 평균수명=("수명일", "mean"))
    lc = csm[live].groupby("제작월")["소재"].nunique()
    summ["LIVE소재수량"] = lc.reindex(summ.index).fillna(0).astype(int)
    summ["CPA"] = (summ["지출"] / summ["전환"]).where(summ["전환"] > 0)
    summ["CTR"] = (summ["클릭"] / summ["노출"] * 100).where(summ["노출"] > 0)
    summ["CVR"] = (summ["전환"] / summ["클릭"] * 100).where(summ["클릭"] > 0)
    summ = summ.reset_index()
    show = summ[["제작월", "제작소재수량", "LIVE소재수량", "평균수명", "지출", "노출", "클릭", "전환", "CPA", "CTR", "CVR"]].copy()
    show["지출"] = show["지출"].round(0)
    show["CPA"] = show["CPA"].round(0)
    show["평균수명"] = show["평균수명"].round(0)
    st.dataframe(show, use_container_width=True, hide_index=True, column_config={
        "평균수명": st.column_config.NumberColumn("평균수명(일)", format="%.0f"),
        "지출": st.column_config.NumberColumn("지출(₩)", format="localized"),
        "노출": st.column_config.NumberColumn(format="localized"),
        "클릭": st.column_config.NumberColumn(format="localized"),
        "CPA": st.column_config.NumberColumn("CPA(₩)", format="localized"),
        "CTR": st.column_config.NumberColumn(format="%.2f%%"),
        "CVR": st.column_config.NumberColumn(format="%.2f%%")})
    b, l = st.columns(2)
    with b:
        st.markdown("**제작월별 소재 수 (제작 vs LIVE)**")
        f = go.Figure()
        f.add_bar(x=summ["제작월"], y=summ["제작소재수량"], name="제작", marker_color=BLUE)
        f.add_bar(x=summ["제작월"], y=summ["LIVE소재수량"], name="LIVE", marker_color=GREEN)
        f.update_layout(height=340, barmode="group", margin=dict(t=30, b=10),
                        legend=dict(orientation="h", y=1.15), yaxis_title="소재 수")
        st.plotly_chart(f, use_container_width=True)
    with l:
        st.markdown("**제작월별 CPA / CTR**")
        f = go.Figure()
        f.add_scatter(x=summ["제작월"], y=summ["CPA"], name="CPA", mode="lines+markers", line=dict(color=RED, width=3))
        f.add_scatter(x=summ["제작월"], y=summ["CTR"], name="CTR%", mode="lines+markers", line=dict(color=BLUE), yaxis="y2")
        f.update_layout(height=340, margin=dict(t=30, b=10), yaxis=dict(title="CPA"),
                        yaxis2=dict(title="CTR%", overlaying="y", side="right"),
                        legend=dict(orientation="h", y=1.15))
        st.plotly_chart(f, use_container_width=True)

# ─────────────────────────── ③ 제작월별 진단 ───────────────────────────
with tabs[2]:
    st.subheader("제작월별 소재 진단")
    cs2 = cs.copy()
    cs2["제작월"] = cs2["최초집행"].dt.to_period("M").astype(str)
    months = ["모두보기"] + sorted(cs2["제작월"].dropna().unique(), reverse=True)
    mo = st.selectbox("제작월 선택", months, index=0)
    cohort_cs = cs2 if mo == "모두보기" else cs2[cs2["제작월"] == mo]
    cohort = cohort_cs["소재"].tolist()
    sub = df[df["소재"].isin(cohort)]
    st.caption(f"{mo} · 소재 {len(cohort)}개 · 지출 ₩{sub['spend'].sum():,.0f} · 구매 {int(sub['omni_purchase'].sum()):,}건")

    freq_label = st.radio("주기", ["주", "월"], horizontal=True, index=0, key="cohort_freq")
    freq = {"주": "W-MON", "월": "MS"}[freq_label]
    t = resample_metrics(sub, freq)
    a, b = st.columns(2)
    with a:
        spend_cpa_chart(t, f"{mo} 묶음 — 지출 vs CPA 변화", "coh_sc")
    with b:
        ctr_cvr_chart(t, f"{mo} 묶음 — CTR / CVR 변화", "coh_cc")

    st.divider()
    st.markdown("**소재 목록** (행 클릭 → 아래에 그 소재 추이)")
    disp = cohort_cs[["소재", "최초집행", "최종집행", "수명일", "광고수", "캠페인수", "노출", "클릭",
                      "지출", "구매_웹", "구매_오프", "구매_전체", "CPA", "CTR", "CVR"]].copy()
    disp["최초집행"] = disp["최초집행"].dt.date
    disp["최종집행"] = disp["최종집행"].dt.date
    disp["지출"] = disp["지출"].round(0)
    disp["CPA"] = disp["CPA"].round(0)
    disp = disp.sort_values("지출", ascending=False).reset_index(drop=True)
    event = st.dataframe(
        disp, use_container_width=True, hide_index=True, height=380,
        on_select="rerun", selection_mode="single-row", key="ctbl",
        column_config={
            "노출": st.column_config.NumberColumn(format="localized"),
            "클릭": st.column_config.NumberColumn(format="localized"),
            "지출": st.column_config.NumberColumn("지출(₩)", format="localized"),
            "CPA": st.column_config.NumberColumn("CPA(₩)", format="localized"),
            "CTR": st.column_config.NumberColumn(format="%.2f%%"),
            "CVR": st.column_config.NumberColumn(format="%.2f%%"),
        })
    try:
        rows = [r for r in event.selection["rows"] if r < len(disp)]
    except Exception:
        rows = []
    sel = disp.iloc[rows[0]]["소재"] if rows else (disp.iloc[0]["소재"] if len(disp) else None)

    if sel is not None:
        st.divider()
        st.subheader(f"소재 효율 추이 · {sel}")
        one = resample_metrics(df[df["소재"] == sel], "W-MON")
        d1, d2 = st.columns(2)
        with d1:
            spend_cpa_chart(one, "주별 지출 vs CPA", "drl_sc")
        with d2:
            ctr_cvr_chart(one, "주별 CTR / CVR", "drl_cc")

# ─────────────────────────── ④ 메타 효율 추이 ───────────────────────────
with tabs[3]:
    st.subheader("메타 효율 시계열")
    freq_label = st.radio("주기", ["일", "주", "월"], horizontal=True, index=1, key="eff_freq")
    freq = {"일": "D", "주": "W-MON", "월": "MS"}[freq_label]
    t = resample_metrics(df, freq)
    fig = go.Figure()
    fig.add_bar(x=t["date"], y=t["지출"], name="지출", marker_color="#bfdbfe")
    fig.add_scatter(x=t["date"], y=t["CPA"], name="CPA", mode="lines+markers",
                    line=dict(color=RED, width=3), yaxis="y2")
    fig.update_layout(height=360, margin=dict(t=30, b=10), yaxis=dict(title="지출"),
                      yaxis2=dict(title="CPA", overlaying="y", side="right"),
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        f = go.Figure()
        f.add_scatter(x=t["date"], y=t["CTR"], name="CTR%", line=dict(color=BLUE))
        f.add_scatter(x=t["date"], y=t["CVR"], name="CVR%", line=dict(color=GREEN))
        f.update_layout(height=300, margin=dict(t=36, b=10), title="CTR / CVR (%)",
                        legend=dict(orientation="h", y=1.16))
        st.plotly_chart(f, use_container_width=True)
    with c2:
        f = go.Figure(go.Scatter(x=t["date"], y=t["CPM"], name="CPM", line=dict(color=AMBER)))
        f.update_layout(height=300, margin=dict(t=36, b=10), title="CPM (매체 단가)")
        st.plotly_chart(f, use_container_width=True)

# ─────────────────────────── ⑤ 소재 생존·품질 ───────────────────────────
with tabs[4]:
    st.subheader("소재 생존곡선 (수명 ≥ N일 비율)")
    life = cs["수명일"].dropna()
    ks = list(range(0, int(min(life.max(), 180)) + 1, 3)) if len(life) else [0]
    surv = [(life >= k).mean() * 100 for k in ks]
    fig = go.Figure(go.Scatter(x=ks, y=surv, mode="lines", fill="tozeroy", line=dict(color=BLUE)))
    fig.update_layout(height=320, margin=dict(t=20, b=10), xaxis_title="일수 K", yaxis_title="생존율 (%)")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("※ 최근 제작 소재는 절단(censoring)으로 수명이 짧게 잡힘.")
    cs3 = cs.copy()
    cs3["제작월"] = cs3["최초집행"].dt.to_period("M").astype(str)
    q1, q2 = st.columns(2)
    with q1:
        st.subheader("제작월별 평균 CTR")
        mm = cs3.dropna(subset=["CTR"]).groupby("제작월").apply(
            lambda x: (x["클릭"].sum() / x["노출"].sum() * 100) if x["노출"].sum() else 0).reset_index(name="CTR")
        f = px.bar(mm, x="제작월", y="CTR", color_discrete_sequence=[BLUE])
        f.update_layout(height=320, margin=dict(t=20, b=10), yaxis_title="CTR (%)")
        st.plotly_chart(f, use_container_width=True)
    with q2:
        st.subheader("제작월별 소재 수명 분포")
        cs3["구간"] = pd.cut(cs3["수명일"], [0, 14, 29, 10**9], labels=["단기≤14", "중기15-29", "장기≥30"])
        dist = cs3.groupby(["제작월", "구간"], observed=True).size().reset_index(name="n")
        f = px.bar(dist, x="제작월", y="n", color="구간", barmode="stack",
                   color_discrete_map={"단기≤14": "#fca5a5", "중기15-29": "#fde047", "장기≥30": GREEN})
        f.update_layout(height=320, margin=dict(t=20, b=10), yaxis_title="소재 수")
        st.plotly_chart(f, use_container_width=True)
