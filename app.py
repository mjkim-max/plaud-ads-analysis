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


def spend_cpa_ctr_chart(t, title, key):
    f = go.Figure()
    f.add_bar(x=t["date"], y=t["지출"], name="지출", marker_color="#bfdbfe")
    f.add_scatter(x=t["date"], y=t["CPA"], name="CPA", mode="lines+markers", line=dict(color=RED, width=2), yaxis="y2")
    f.add_scatter(x=t["date"], y=t["CTR"], name="CTR%", mode="lines+markers", line=dict(color=BLUE, width=2), yaxis="y3")
    f.update_layout(height=360, margin=dict(t=44, b=10), xaxis=dict(domain=[0, 0.86]),
                    yaxis=dict(title="지출"), yaxis2=dict(title="CPA", overlaying="y", side="right"),
                    yaxis3=dict(title="CTR%", overlaying="y", side="right", anchor="free", position=1.0, showgrid=False),
                    legend=dict(orientation="h", y=1.14, x=0))
    st.markdown(f"**{title}**")
    st.plotly_chart(f, use_container_width=True, key=key)


def imp_ctr_cvr_chart(t, title, key):
    f = go.Figure()
    f.add_bar(x=t["date"], y=t["노출"], name="노출", marker_color="#fde68a")
    f.add_scatter(x=t["date"], y=t["CTR"], name="CTR%", mode="lines+markers", line=dict(color=BLUE, width=2), yaxis="y2")
    f.add_scatter(x=t["date"], y=t["CVR"], name="CVR%", mode="lines+markers", line=dict(color=GREEN, width=2), yaxis="y2")
    f.update_layout(height=360, margin=dict(t=44, b=10), yaxis=dict(title="노출"),
                    yaxis2=dict(title="%", overlaying="y", side="right"),
                    legend=dict(orientation="h", y=1.14, x=0))
    st.markdown(f"**{title}**")
    st.plotly_chart(f, use_container_width=True, key=key)


cs = creative_summary(df)

st.title("📊 PLAUD 광고 성과 대시보드")
st.caption(f"소재 단위 지표 · 데이터 {dmin} ~ {dmax} (매일 자동 갱신)")

VIEWS = ["① 개요", "② 월별 소재 컨디션", "③ 제작월별 진단", "④ 구글×메타 교차분석", "⑤ 제작×집행 매트릭스", "⑥ 채널 매출·ROAS", "⑦ 보고(월별 종합)", "⑧ 소재 상태(4분류)"]
view = st.radio("화면", VIEWS, horizontal=True, key="view", label_visibility="collapsed")

# ─────────────────────────── ① 개요 ───────────────────────────
if view == VIEWS[0]:
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
elif view == VIEWS[1]:
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

    st.divider()
    st.subheader("소재 생존곡선 (수명 ≥ N일 비율)")
    life = cs["수명일"].dropna()
    ks = list(range(0, int(min(life.max(), 180)) + 1, 3)) if len(life) else [0]
    surv = [(life >= k).mean() * 100 for k in ks]
    figS = go.Figure(go.Scatter(x=ks, y=surv, mode="lines", fill="tozeroy", line=dict(color=BLUE)))
    figS.update_layout(height=300, margin=dict(t=20, b=10), xaxis_title="일수 K", yaxis_title="생존율 (%)")
    st.plotly_chart(figS, use_container_width=True, key="surv_curve")
    st.caption("※ 최근 제작 소재는 절단(censoring)으로 수명이 짧게 잡힘.")
    cs3 = cs.copy()
    cs3["제작월"] = cs3["최초집행"].dt.to_period("M").astype(str)
    q1, q2 = st.columns(2)
    with q1:
        st.markdown("**제작월별 평균 CTR**")
        mm = cs3.dropna(subset=["CTR"]).groupby("제작월").apply(
            lambda x: (x["클릭"].sum() / x["노출"].sum() * 100) if x["노출"].sum() else 0).reset_index(name="CTR")
        fq1 = px.bar(mm, x="제작월", y="CTR", color_discrete_sequence=[BLUE])
        fq1.update_layout(height=300, margin=dict(t=20, b=10), yaxis_title="CTR (%)")
        st.plotly_chart(fq1, use_container_width=True, key="qual_ctr")
    with q2:
        st.markdown("**제작월별 소재 수명 분포**")
        cs3["구간"] = pd.cut(cs3["수명일"], [0, 14, 29, 10**9], labels=["단기≤14", "중기15-29", "장기≥30"])
        dist = cs3.groupby(["제작월", "구간"], observed=True).size().reset_index(name="n")
        fq2 = px.bar(dist, x="제작월", y="n", color="구간", barmode="stack",
                     color_discrete_map={"단기≤14": "#fca5a5", "중기15-29": "#fde047", "장기≥30": GREEN})
        fq2.update_layout(height=300, margin=dict(t=20, b=10), yaxis_title="소재 수")
        st.plotly_chart(fq2, use_container_width=True, key="qual_life")

# ─────────────────────────── ③ 제작월별 진단 ───────────────────────────
elif view == VIEWS[2]:
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
        spend_cpa_ctr_chart(t, f"{mo} 묶음 — 지출·CPA·CTR", "coh_1")
    with b:
        imp_ctr_cvr_chart(t, f"{mo} 묶음 — 노출·CTR·CVR", "coh_2")

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
        c1, c2 = st.columns(2)
        with c1:
            spend_cpa_ctr_chart(one, "주별 지출·CPA·CTR", "drl_1")
        with c2:
            imp_ctr_cvr_chart(one, "주별 노출·CTR·CVR", "drl_2")
        st.caption("노출이 쌓이는데 CTR·CVR이 떨어지면 → 소재 소진(피로) 신호.")

# ─────────────────────────── ④ 구글×메타 교차분석 ───────────────────────────
elif view == VIEWS[3]:
    st.subheader("구글 디멘드젠 → 메타 효율 (교차분석)")
    st.caption("가설: 구글 디멘드젠 노출·클릭 ↑ → 메타 CTR·CVR ↑. 주 단위로 검증. "
               "(상관 ≠ 인과 — 같은 시기 소재 변화 등 교란 가능)")
    try:
        g = dl.load_google_daily()
    except Exception:
        g = pd.DataFrame()
    if g.empty or "channel" not in g.columns:
        st.warning("google_일별(채널 포함) 데이터가 아직 없습니다. 수집 후 표시됩니다.")
    else:
        if isinstance(rng, tuple) and len(rng) == 2:
            g = g[(g["date"].dt.date >= rng[0]) & (g["date"].dt.date <= rng[1])]
        chan_map = {"디멘드젠": ["DEMAND_GEN", "DISCOVERY"], "PMax": ["PERFORMANCE_MAX"],
                    "검색": ["SEARCH"], "디스플레이": ["DISPLAY"], "동영상": ["VIDEO"]}
        cc = st.columns(4)
        gch = cc[0].selectbox("구글 채널", list(chan_map) + ["전체 구글"], index=0)
        gmet = cc[1].selectbox("구글 지표", ["노출", "클릭", "비용"], index=0)
        mmet = cc[2].selectbox("메타 지표", ["CVR", "CTR", "CPA"], index=0)
        lag = cc[3].selectbox("구글 선행(주)", [0, 1, 2], index=0,
                              help="구글 지표를 N주 앞선 값으로 메타와 맞춤(선행효과 확인).")

        gcol = {"노출": "impressions", "클릭": "clicks", "비용": "cost"}[gmet]
        gg = g if gch == "전체 구글" else g[g["channel"].isin(chan_map[gch])]
        gw = gg.set_index("date").resample("W-MON").agg(구글=(gcol, "sum")).reset_index()
        mw = df.set_index("date").resample("W-MON").agg(
            imp=("impressions", "sum"), clk=("clicks", "sum"),
            omni=("omni_purchase", "sum"), sp=("spend", "sum")).reset_index()
        mw["CTR"] = (mw["clk"] / mw["imp"] * 100).where(mw["imp"] > 0)
        mw["CVR"] = (mw["omni"] / mw["clk"] * 100).where(mw["clk"] > 0)
        mw["CPA"] = (mw["sp"] / mw["omni"]).where(mw["omni"] > 0)
        merged = pd.merge(gw, mw[["date", "CTR", "CVR", "CPA"]], on="date", how="inner").sort_values("date")
        merged["_g"] = merged["구글"].shift(lag)
        merged["_m"] = merged[mmet]
        d = merged.dropna(subset=["_g", "_m"])

        if len(d) < 3:
            st.info("겹치는 주간 데이터가 부족합니다.")
        else:
            level_r = d["_g"].corr(d["_m"])
            chg_r = d["_g"].diff().corr(d["_m"].diff())
            k1, k2, k3 = st.columns(3)
            k1.metric("수준 상관", f"{level_r:+.2f}")
            k2.metric("증감 상관", f"{chg_r:+.2f}", help="전주 대비 변화끼리 — 인과 판단은 이걸 더 신뢰")
            k3.metric("겹친 주", f"{len(d)}주")

            strength = "강함" if abs(chg_r) >= 0.5 else ("약함" if abs(chg_r) >= 0.3 else "거의 없음")
            note = f"디멘드젠 {gmet}과 메타 {mmet}의 **증감상관 {chg_r:+.2f}** ({strength})."
            if mmet == "CPA":
                note += " CPA는 낮을수록 좋음 → **음(−)이면 디멘드젠이 CPA 개선**에 도움."
            st.info(note + " · 상관≠인과: 같은 주 소재 변화 등 교란 가능.")

            st.markdown(f"**주별 — 구글 {gch} {gmet} vs 메타 {mmet}**")
            f = go.Figure()
            f.add_bar(x=merged["date"], y=merged["구글"], name=f"구글 {gmet}", marker_color="#c7d2fe")
            f.add_scatter(x=merged["date"], y=merged[mmet], name=f"메타 {mmet}", mode="lines+markers",
                          line=dict(color=RED, width=3), yaxis="y2")
            f.update_layout(height=380, margin=dict(t=30, b=10), yaxis=dict(title=f"구글 {gmet}"),
                            yaxis2=dict(title=f"메타 {mmet}", overlaying="y", side="right"),
                            legend=dict(orientation="h", y=1.12))
            st.plotly_chart(f, use_container_width=True, key="cross_ts")

            st.markdown(f"**산점도 — 구글 {gmet}(선행 {lag}주) vs 메타 {mmet}**")
            sc = px.scatter(d, x="_g", y="_m", color_discrete_sequence=[BLUE])
            if d["_g"].var() > 0:
                slope = d["_g"].cov(d["_m"]) / d["_g"].var()
                intercept = d["_m"].mean() - slope * d["_g"].mean()
                xs = [d["_g"].min(), d["_g"].max()]
                sc.add_scatter(x=xs, y=[slope * x + intercept for x in xs], mode="lines",
                               line=dict(color=RED), name="추세")
            sc.update_layout(height=380, margin=dict(t=20, b=10),
                             xaxis_title=f"구글 {gmet}", yaxis_title=f"메타 {mmet}")
            st.plotly_chart(sc, use_container_width=True, key="cross_sc")

# ─────────────────────────── ⑤ 제작×집행 매트릭스 ───────────────────────────
elif view == VIEWS[4]:
    st.subheader("제작월 × 집행월 매트릭스")
    st.caption("행=제작월(소재 만든 달) · 열=집행월 · 셀=선택 지표 · 합계 포함. "
               "(제작 이전 집행은 없어 상삼각은 비어있음)")
    metric = st.selectbox("지표", ["소재수", "노출", "클릭", "전환", "지출", "CPM", "CPC", "CVR", "CPA"], key="mx_metric")

    prod = cs.set_index("소재")["최초집행"].dt.to_period("M").astype(str)
    base = df.copy()
    base["제작월"] = base["소재"].map(prod)
    base["집행월"] = base["date"].dt.to_period("M").astype(str)
    base = base.dropna(subset=["제작월"])
    months = sorted(set(base["제작월"]) | set(base["집행월"]))

    if metric == "소재수":
        # 셀 = 그 (제작월 코호트)에서 그 집행월에 켜져있던(지출>0) 소재 수
        act = base[base["spend"] > 0]
        mat = act.groupby(["제작월", "집행월"])["소재"].nunique().unstack("집행월").reindex(index=months, columns=months)
        row_tot = act.groupby("제작월")["소재"].nunique().reindex(months)   # 코호트 전체 소재수(고유)
        col_tot = act.groupby("집행월")["소재"].nunique().reindex(months)   # 그 달 켜진 소재수(고유)
        grand = act["소재"].nunique()
        mat["합계"] = row_tot
        col_tot["합계"] = grand
        mat.loc["합계"] = col_tot
    else:
        gb = base.groupby(["제작월", "집행월"]).agg(
            노출=("impressions", "sum"), 클릭=("clicks", "sum"),
            전환=("omni_purchase", "sum"), 지출=("spend", "sum"))
        P = {k: gb[k].unstack("집행월").reindex(index=months, columns=months).fillna(0)
             for k in ["노출", "클릭", "전환", "지출"]}

        def _safe(num, den):
            if isinstance(den, (pd.Series, pd.DataFrame)):
                return (num / den).where(den > 0)
            return (num / den) if den else float("nan")

        def _mfn(imp, clk, conv, sp):
            return {"노출": imp, "클릭": clk, "전환": conv, "지출": sp,
                    "CPM": _safe(sp * 1000, imp), "CPC": _safe(sp, clk),
                    "CVR": _safe(conv * 100, clk), "CPA": _safe(sp, conv)}[metric]

        mat = _mfn(P["노출"], P["클릭"], P["전환"], P["지출"])
        mat = mat.mask((P["노출"] + P["클릭"] + P["전환"] + P["지출"]) == 0)
        row_tot = _mfn(P["노출"].sum(1), P["클릭"].sum(1), P["전환"].sum(1), P["지출"].sum(1))
        col_tot = _mfn(P["노출"].sum(0), P["클릭"].sum(0), P["전환"].sum(0), P["지출"].sum(0))
        grand = _mfn(P["노출"].values.sum(), P["클릭"].values.sum(),
                     P["전환"].values.sum(), P["지출"].values.sum())
        mat["합계"] = row_tot
        col_tot["합계"] = grand
        mat.loc["합계"] = col_tot
    def _cell(v):
        if pd.isna(v):
            return ""
        return f"{v:.2f}" if metric == "CVR" else f"{v:,.0f}"

    disp = mat.apply(lambda c: c.map(_cell)).reset_index()
    st.dataframe(disp, use_container_width=True, hide_index=True, height=600)

# ─────────────────────────── ⑥ 채널 매출·ROAS ───────────────────────────
elif view == VIEWS[5]:
    st.subheader("채널 매출 · ROAS")
    sales = dl.load_channel_sales()
    if sales.empty:
        st.warning("채널별 매출 데이터가 없습니다.")
    else:
        if isinstance(rng, tuple) and len(rng) == 2:
            sales = sales[(sales["date"].dt.date >= rng[0]) & (sales["date"].dt.date <= rng[1])]
        CH_COLORS = {"자사몰": BLUE, "네이버": GREEN, "쿠팡": AMBER, "기타": GRAY}
        order = ["자사몰", "네이버", "쿠팡", "기타"]

        # ── A. 비중 ──
        st.markdown("### A. 채널 매출 비중")
        by = sales.groupby("channel")["sales"].sum().reindex(order).fillna(0)
        a1, a2 = st.columns([2, 3])
        with a1:
            fig = go.Figure(go.Pie(labels=list(by.index), values=list(by.values), hole=0.5,
                                   marker_colors=[CH_COLORS[c] for c in by.index]))
            fig.update_layout(height=320, margin=dict(t=30, b=10), title="기간 합계 비중")
            st.plotly_chart(fig, use_container_width=True, key="ch_donut")
        with a2:
            mo = sales.set_index("date").groupby("channel")["sales"].resample("MS").sum().reset_index()
            fig = px.area(mo, x="date", y="sales", color="channel", color_discrete_map=CH_COLORS,
                          category_orders={"channel": order})
            fig.update_layout(height=320, margin=dict(t=30, b=10), title="월별 채널 판매(누적)", yaxis_title="판매 건수")
            st.plotly_chart(fig, use_container_width=True, key="ch_area")

        # ── B. 추이 ──
        st.markdown("### B. 채널별 판매 추이")
        fl = st.radio("주기", ["주", "월"], horizontal=True, index=0, key="sales_freq")
        tr = sales.set_index("date").groupby("channel")["sales"].resample({"주": "W-MON", "월": "MS"}[fl]).sum().reset_index()
        fig = px.line(tr, x="date", y="sales", color="channel", color_discrete_map=CH_COLORS,
                      category_orders={"channel": order}, markers=True)
        fig.update_layout(height=360, margin=dict(t=20, b=10), yaxis_title="판매 건수")
        st.plotly_chart(fig, use_container_width=True, key="ch_line")

        # ── C. 자사몰 효율 (ROAS) ──
        st.markdown("### C. 자사몰 효율 — 광고비 vs 자사몰 판매")
        st.caption("광고는 자사몰에 귀인(가정). 총 광고비(메타+구글) 대비 자사몰 판매·건당 광고비.")
        g = dl.load_google_daily()
        if not g.empty and isinstance(rng, tuple) and len(rng) == 2:
            g = g[(g["date"].dt.date >= rng[0]) & (g["date"].dt.date <= rng[1])]
        msp = df.groupby("date")["spend"].sum().rename("meta")
        gsp = (g.groupby("date")["cost"].sum() if not g.empty else pd.Series(dtype=float)).rename("google")
        jmall = sales[sales["channel"] == "자사몰"].groupby("date")["sales"].sum().rename("자사몰판매")
        daily = pd.concat([msp, gsp, jmall], axis=1).fillna(0)
        daily["광고비"] = daily["meta"] + daily["google"]
        wk = daily.resample("W-MON").sum()
        wk = wk[wk["광고비"] > 0]
        wk["건당광고비"] = (wk["광고비"] / wk["자사몰판매"]).where(wk["자사몰판매"] > 0)

        fig = go.Figure()
        fig.add_bar(x=wk.index, y=wk["광고비"], name="광고비(메타+구글)", marker_color="#bfdbfe")
        fig.add_scatter(x=wk.index, y=wk["자사몰판매"], name="자사몰 판매", mode="lines+markers",
                        line=dict(color=BLUE, width=3), yaxis="y2")
        fig.update_layout(height=360, margin=dict(t=30, b=10), yaxis=dict(title="광고비"),
                          yaxis2=dict(title="자사몰 판매(건)", overlaying="y", side="right"),
                          legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig, use_container_width=True, key="roas_ts")
        fig2 = go.Figure(go.Scatter(x=wk.index, y=wk["건당광고비"], mode="lines+markers", line=dict(color=RED, width=3)))
        fig2.update_layout(height=300, margin=dict(t=30, b=10), title="자사몰 판매 1건당 광고비 (₩)")
        st.plotly_chart(fig2, use_container_width=True, key="roas_cpa")

# ─────────────────────────── ⑦ 보고 (월별 종합) ───────────────────────────
elif view == VIEWS[6]:
    st.subheader("보고 — 월별 종합 요약")
    g = dl.load_google_daily()
    sales = dl.load_channel_sales()
    if isinstance(rng, tuple) and len(rng) == 2:
        if not g.empty:
            g = g[(g["date"].dt.date >= rng[0]) & (g["date"].dt.date <= rng[1])]
        if not sales.empty:
            sales = sales[(sales["date"].dt.date >= rng[0]) & (sales["date"].dt.date <= rng[1])]

    md = df.copy(); md["월"] = md["date"].dt.to_period("M").astype(str)
    mm = md.groupby("월").agg(메타지출=("spend", "sum"), 노출=("impressions", "sum"),
                             클릭=("clicks", "sum"), 구매=("omni_purchase", "sum"))
    if not g.empty:
        gd = g.copy(); gd["월"] = gd["date"].dt.to_period("M").astype(str)
        gg = gd.groupby("월")["cost"].sum().rename("구글비용")
    else:
        gg = pd.Series(dtype=float, name="구글비용")
    if not sales.empty:
        sd = sales.copy(); sd["월"] = sd["date"].dt.to_period("M").astype(str)
        sp = sd.pivot_table(index="월", columns="channel", values="sales", aggfunc="sum")
    else:
        sp = pd.DataFrame()

    rep = mm.join(gg, how="outer").join(sp, how="outer").fillna(0).sort_index()
    for c in ["자사몰", "네이버", "쿠팡"]:
        if c not in rep.columns:
            rep[c] = 0
    rep["총광고비"] = rep["메타지출"] + rep["구글비용"]
    rep["3채널판매"] = rep["자사몰"] + rep["네이버"] + rep["쿠팡"]
    rep["메타CPA"] = (rep["메타지출"] / rep["구매"]).where(rep["구매"] > 0)
    rep["메타CTR"] = (rep["클릭"] / rep["노출"] * 100).where(rep["노출"] > 0)
    rep["자사몰건당광고비"] = (rep["총광고비"] / rep["자사몰"]).where(rep["자사몰"] > 0)

    # 기간 KPI
    tot_ad, jm, ch3 = rep["총광고비"].sum(), rep["자사몰"].sum(), rep["3채널판매"].sum()
    omni, mspend = rep["구매"].sum(), rep["메타지출"].sum()
    k = st.columns(5)
    k[0].metric("총 광고비", f"₩{tot_ad/1e8:.2f}억")
    k[1].metric("3채널 판매", f"{int(ch3):,}건")
    k[2].metric("자사몰 판매", f"{int(jm):,}건")
    k[3].metric("자사몰 건당광고비", f"₩{tot_ad/jm/1e4:,.1f}만" if jm else "-")
    k[4].metric("메타 CPA", f"₩{mspend/omni/1e4:,.1f}만" if omni else "-")
    st.divider()

    cols = ["메타지출", "구글비용", "총광고비", "자사몰", "네이버", "쿠팡", "3채널판매", "메타CPA", "메타CTR", "자사몰건당광고비"]
    disp = rep[cols].reset_index().rename(columns={"index": "월"})
    for c in ["메타지출", "구글비용", "총광고비", "메타CPA", "자사몰건당광고비"]:
        disp[c] = disp[c].round(0)
    won = {c: st.column_config.NumberColumn(c, format="localized") for c in ["메타지출", "구글비용", "총광고비", "메타CPA", "자사몰건당광고비"]}
    won["메타CTR"] = st.column_config.NumberColumn(format="%.2f%%")
    st.dataframe(disp, use_container_width=True, hide_index=True, height=520, column_config=won)
    st.caption("월별: 메타·구글 광고비 + 채널 판매 + 메타 CPA/CTR + 자사몰 건당 광고비. 보고서용 종합표.")

# ─────────────────────────── ⑧ 소재 상태 (4분류) ───────────────────────────
elif view == VIEWS[7]:
    st.subheader("소재 상태 분류")
    st.caption("기준은 직접 조절 — 활성일(최근 N일 집행=돌고있는), CPA(이 값 이하=가능성 있음).")
    cc = st.columns(4)
    active_days = cc[0].number_input("활성 기준(일)", 1, 90, 14, step=1,
                                     help="최종 집행이 최근 N일 이내면 '지금 돌고있는'")
    med = cs.loc[cs["CPA"].notna(), "CPA"].median()
    cpa_thr = cc[1].number_input("가능성 CPA 기준(₩)", 0, 10_000_000,
                                 int(med) if not pd.isna(med) else 120000, step=10000,
                                 help="안 도는 소재 중 CPA가 이 값 이하면 '가능성 있음'")
    budget_thr = cc[2].number_input("예산 기준치(₩)", 0, 100_000_000, 1_000_000, step=100_000,
                                    help="가능성 낮은 소재 중 지출이 이 값 미만이면 '추가 기회 필요'")
    hide_image = cc[3].checkbox("[이미지] 소재 제외", value=False,
                                help="소재명이 '[이미지]'로 시작하는 소재를 표에서 숨김")

    c = cs.copy()
    if hide_image:
        _img = c["소재"].astype(str).str.strip().str.startswith("[이미지]")
        st.caption(f"[이미지] 소재 {int(_img.sum())}개 제외됨")
        c = c[~_img]

    # 계약종료(집행 불가) 소재: 성과 기준 분류(①~④)에서 빼고 ⑤로 별도 표시
    ended = dl.load_contract_ended()
    is_ended = c["소재"].astype(str).str.strip().isin(ended)

    active = c["최종집행"] >= (max_date - pd.Timedelta(days=active_days))
    good = c["CPA"].notna() & (c["CPA"] <= cpa_thr)
    c["상태"] = "④"
    c.loc[~active & ~good & (c["지출"] < budget_thr), "상태"] = "③"
    c.loc[~active & good, "상태"] = "②"
    c.loc[active, "상태"] = "①"
    c.loc[is_ended, "상태"] = "⑤"   # 계약종료는 성과 무관하게 우선 분류

    cols = ["소재", "최초집행", "최종집행", "수명일", "광고수", "캠페인수", "노출",
            "지출", "구매_전체", "CPA", "CTR", "CVR"]
    cfg = {
        "노출": st.column_config.NumberColumn(format="localized"),
        "지출": st.column_config.NumberColumn("지출(₩)", format="localized"),
        "CPA": st.column_config.NumberColumn("CPA(₩)", format="localized"),
        "CTR": st.column_config.NumberColumn(format="%.2f%%"),
        "CVR": st.column_config.NumberColumn(format="%.2f%%"),
    }

    def show_group(code, title, hint):
        sub = c[c["상태"] == code][cols].copy()
        st.markdown(f"### {title} — {len(sub)}개")
        st.caption(hint)
        if sub.empty:                      # 빈 표를 Arrow로 렌더하면 세그폴트 → 표 생략
            st.caption("— 해당 소재 없음 —")
            return
        # 날짜는 문자열로(‘date’ object 컬럼이 Arrow 변환에서 크래시하는 환경 회피)
        sub["최초집행"] = sub["최초집행"].dt.strftime("%Y-%m-%d")
        sub["최종집행"] = sub["최종집행"].dt.strftime("%Y-%m-%d")
        sub["지출"] = sub["지출"].round(0)
        sub["CPA"] = sub["CPA"].round(0)
        sub = sub.sort_values("지출", ascending=False).reset_index(drop=True)
        st.dataframe(sub, use_container_width=True, hide_index=True, height=300, column_config=cfg)

    show_group("①", "① 광고 집행 O", f"최근 {active_days}일 내 집행 중.")
    show_group("②", "② 광고 집행 X │ CPA O", f"현재 안 돎 + CPA ≤ ₩{cpa_thr:,} (재집행/증액 후보).")
    show_group("③", "③ 광고 집행 X │ CPA X │ SPEND O", f"현재 안 돎 + CPA 기준 초과 + 지출 < ₩{budget_thr:,} (아직 덜 검증 → 추가 기회).")
    show_group("④", "④ 광고 집행 X │ CPA X │ SPEND X", f"현재 안 돎 + CPA 기준 초과 + 지출 ≥ ₩{budget_thr:,} (충분히 태웠는데 부진 → 정리).")
    show_group("⑤", "⑤ 집행 불가", "계약 만료 등으로 못 도는 소재(성과 무관). `소재_계약종료` 시트 탭에서 관리 → ①~④에서 자동 제외.")
    st.link_button(
        "📝 계약종료 리스트 편집 (구글시트 열기)",
        "https://docs.google.com/spreadsheets/d/1l6GB0Bow6m2wimf-aNZJwnkoAqtwIpqPX6en8Wx2kcg/edit?gid=1487400031#gid=1487400031",
    )
