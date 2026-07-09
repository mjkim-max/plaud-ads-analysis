"""PLAUD 광고 성과 대시보드 (Streamlit) — 라이브 Google Sheets 기반.

데이터: meta_소재일별 (매일 자동 수집). 소재(정규명) 단위로 묶어 광고이름 파편화를 해소.
근거 분석: 광고분석_종합정리.md / 광고분석_대시보드_가이드(_보강분).md
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import data_loader as dl

st.set_page_config(page_title="PLAUD 광고 대시보드", page_icon="📊", layout="wide")

ACTIVE_WINDOW = 14   # 최근 N일 집행 = 활성
BLUE, GREEN, AMBER, GRAY, RED = "#2563eb", "#22c55e", "#f59e0b", "#9ca3af", "#ef4444"


# ────────────────────────── 데이터 ──────────────────────────
try:
    df = dl.load_meta_daily()
except Exception as e:
    st.error(f"데이터 로드 실패: {e}\n\nStreamlit Secrets에 `gcp_service_account`·`sheet_id`가 있는지 확인하세요.")
    st.stop()

if df.empty:
    st.warning("meta_소재일별 데이터가 비어있습니다.")
    st.stop()

max_date = df["date"].max()

# 사이드바 — 기간 필터
st.sidebar.header("필터")
dmin, dmax = df["date"].min().date(), max_date.date()
rng = st.sidebar.date_input("기간", (dmin, dmax), min_value=dmin, max_value=dmax)
if isinstance(rng, tuple) and len(rng) == 2:
    df = df[(df["date"].dt.date >= rng[0]) & (df["date"].dt.date <= rng[1])]
st.sidebar.caption(f"소재 {df['소재'].nunique()}개 · 광고 {df['ad_name'].nunique()}개 · {len(df):,}행")
st.sidebar.caption(f"최신 데이터: {max_date.date()}")


@st.cache_data(ttl=1800)
def creative_summary(d: pd.DataFrame) -> pd.DataFrame:
    """소재 단위 집계 — 수명·활성·지출·구매3종·통합 CPA."""
    spent = d[d["spend"] > 0].groupby("소재")["date"]
    g = d.groupby("소재")
    s = pd.DataFrame({
        "지출": g["spend"].sum(),
        "노출": g["impressions"].sum(),
        "클릭": g["clicks"].sum(),
        "구매_웹": g["purchase"].sum(),
        "구매_오프": g["offline_purchase"].sum(),
        "구매_전체": g["omni_purchase"].sum(),
        "매출": g["revenue"].sum(),
        "광고수": g["ad_id"].nunique(),
        "최초집행": spent.min(),
        "최종집행": spent.max(),
        "활성일수": spent.nunique(),
    })
    s["수명일"] = (s["최종집행"] - s["최초집행"]).dt.days + 1
    s["CPA"] = (s["지출"] / s["구매_전체"]).where(s["구매_전체"] > 0)
    s["CTR"] = (s["클릭"] / s["노출"]).where(s["노출"] > 0)
    s["CVR"] = (s["구매_전체"] / s["클릭"]).where(s["클릭"] > 0)
    return s.reset_index()


cs = creative_summary(df)
active_mask = cs["최종집행"] >= (max_date - pd.Timedelta(days=ACTIVE_WINDOW))
median_cpa = cs.loc[active_mask & cs["CPA"].notna(), "CPA"].median()
if pd.isna(median_cpa):
    median_cpa = cs["CPA"].median()


def headroom(row) -> str:
    if row["최종집행"] < (max_date - pd.Timedelta(days=ACTIVE_WINDOW)):
        return "⚪ 휴면"
    if pd.isna(row["CPA"]):
        return "🟡 관망(구매無)"
    return "🟢 증액후보" if row["CPA"] <= median_cpa else "🔴 비효율"


cs["집행여력"] = cs.apply(headroom, axis=1)

st.title("📊 PLAUD 광고 성과 대시보드")
st.caption(f"자사몰 매출 우상향이 목표 · 소재(정규명) 단위 분석 · 데이터 {dmin}~{dmax} (자동 갱신)")

tabs = st.tabs(["① 개요", "② 소재 분석", "③ 메타 효율 추이", "④ 소재 생존·품질", "⑤ 캠페인", "⑥ 전략"])

# ─────────────────────────── ① 개요 ───────────────────────────
with tabs[0]:
    tot_spend, tot_omni = df["spend"].sum(), df["omni_purchase"].sum()
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("총 지출", f"₩{tot_spend/1e8:.2f}억")
    c2.metric("총 구매(전체)", f"{int(tot_omni):,}건")
    c3.metric("통합 CPA", f"₩{tot_spend/tot_omni:,.0f}" if tot_omni else "-")
    c4.metric("활성 소재", f"{int(active_mask.sum())}개", f"전체 {len(cs)}개 중")
    c5.metric("🟢 증액후보", f"{int((cs['집행여력']=='🟢 증액후보').sum())}개", delta_color="off")

    st.divider()
    g1, g2 = st.columns([3, 2])
    with g1:
        st.subheader("월별 지출 vs 구매")
        m = df.set_index("date").resample("MS").agg(지출=("spend", "sum"), 구매=("omni_purchase", "sum")).reset_index()
        fig = go.Figure()
        fig.add_bar(x=m["date"], y=m["지출"], name="지출", marker_color=BLUE, yaxis="y")
        fig.add_scatter(x=m["date"], y=m["구매"], name="구매", mode="lines+markers",
                        line=dict(color=GREEN, width=3), yaxis="y2")
        fig.update_layout(height=360, margin=dict(t=20, b=10),
                          yaxis=dict(title="지출"), yaxis2=dict(title="구매", overlaying="y", side="right"),
                          legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig, use_container_width=True)
    with g2:
        st.subheader("지출 상위 소재 Top 10")
        top = cs.nlargest(10, "지출")[["소재", "지출", "CPA"]].copy()
        top["지출"] = top["지출"].round(0)
        top["CPA"] = top["CPA"].round(0)
        st.dataframe(top, use_container_width=True, hide_index=True,
                     column_config={"지출": st.column_config.NumberColumn("지출(₩)", format="localized"),
                                    "CPA": st.column_config.NumberColumn("CPA(₩)", format="localized")})

# ─────────────────────────── ② 소재 분석 ───────────────────────────
with tabs[1]:
    st.subheader("소재 단위 성과 — 수명 · 통합 CPA · 추가 집행 여력")
    st.caption(f"광고이름이 아니라 **소재**로 묶어 봄. 활성 = 최근 {ACTIVE_WINDOW}일 내 집행. "
               f"🟢 증액후보 = 활성 & CPA ≤ 활성소재 중앙값(₩{median_cpa:,.0f}).")

    f1, f2 = st.columns([1, 3])
    only = f1.selectbox("보기", ["전체", "🟢 증액후보", "🔴 비효율", "⚪ 휴면", "🟡 관망(구매無)"])
    view = cs if only == "전체" else cs[cs["집행여력"] == only]

    show = view[["소재", "집행여력", "최초집행", "최종집행", "수명일", "활성일수", "광고수",
                 "지출", "구매_웹", "구매_오프", "구매_전체", "CPA", "CTR", "CVR"]].copy()
    show["최초집행"] = show["최초집행"].dt.date
    show["최종집행"] = show["최종집행"].dt.date
    show["CTR"] = show["CTR"] * 100
    show["CVR"] = show["CVR"] * 100
    show["지출"] = show["지출"].round(0)
    show["CPA"] = show["CPA"].round(0)
    st.dataframe(
        show.sort_values("지출", ascending=False), use_container_width=True, hide_index=True, height=420,
        column_config={
            "지출": st.column_config.NumberColumn("지출(₩)", format="localized"),
            "CPA": st.column_config.NumberColumn("CPA(₩)", format="localized"),
            "CTR": st.column_config.NumberColumn(format="%.2f%%"),
            "CVR": st.column_config.NumberColumn(format="%.2f%%"),
        })

    st.subheader("수명 vs 통합 CPA (버블 = 지출)")
    plot = cs[(cs["구매_전체"] > 0) & (cs["수명일"].notna())]
    fig = px.scatter(plot, x="수명일", y="CPA", size="지출", color="집행여력", hover_name="소재",
                     size_max=40, color_discrete_map={"🟢 증액후보": GREEN, "🔴 비효율": RED,
                                                       "⚪ 휴면": GRAY, "🟡 관망(구매無)": AMBER})
    fig.update_layout(height=420, margin=dict(t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

# ─────────────────────────── ③ 메타 효율 추이 ───────────────────────────
with tabs[2]:
    st.subheader("메타 효율 시계열")
    freq_label = st.radio("주기", ["일", "주", "월"], horizontal=True, index=1)
    freq = {"일": "D", "주": "W-MON", "월": "MS"}[freq_label]
    t = df.set_index("date").resample(freq).agg(
        지출=("spend", "sum"), 노출=("impressions", "sum"), 클릭=("clicks", "sum"),
        구매=("omni_purchase", "sum")).reset_index()
    t = t[t["지출"] > 0]
    t["CPA"] = (t["지출"] / t["구매"]).where(t["구매"] > 0)
    t["CTR"] = (t["클릭"] / t["노출"] * 100).where(t["노출"] > 0)
    t["CVR"] = (t["구매"] / t["클릭"] * 100).where(t["클릭"] > 0)
    t["CPM"] = (t["지출"] / t["노출"] * 1000).where(t["노출"] > 0)

    fig = go.Figure()
    fig.add_bar(x=t["date"], y=t["지출"], name="지출", marker_color="#bfdbfe", yaxis="y")
    fig.add_scatter(x=t["date"], y=t["CPA"], name="CPA", mode="lines+markers",
                    line=dict(color=RED, width=3), yaxis="y2")
    fig.update_layout(height=360, margin=dict(t=20, b=10), yaxis=dict(title="지출"),
                      yaxis2=dict(title="CPA", overlaying="y", side="right"),
                      legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("비용↑인데 CPA↑ = 수확 체감(포화). CPA 원인은 CPM(매체)이 아니라 소재(CTR·CVR).")

    cc1, cc2 = st.columns(2)
    with cc1:
        fig2 = go.Figure()
        fig2.add_scatter(x=t["date"], y=t["CTR"], name="CTR%", line=dict(color=BLUE))
        fig2.add_scatter(x=t["date"], y=t["CVR"], name="CVR%", line=dict(color=GREEN))
        fig2.update_layout(height=300, margin=dict(t=30, b=10), title="CTR / CVR (%)",
                           legend=dict(orientation="h", y=1.15))
        st.plotly_chart(fig2, use_container_width=True)
    with cc2:
        fig3 = go.Figure()
        fig3.add_scatter(x=t["date"], y=t["CPM"], name="CPM", line=dict(color=AMBER))
        fig3.update_layout(height=300, margin=dict(t=30, b=10), title="CPM (매체 단가)")
        st.plotly_chart(fig3, use_container_width=True)

# ─────────────────────────── ④ 소재 생존·품질 ───────────────────────────
with tabs[3]:
    st.subheader("소재 생존곡선 (수명 ≥ N일 비율)")
    life = cs["수명일"].dropna()
    ks = list(range(0, int(min(life.max(), 120)) + 1, 3)) or [0]
    surv = [(life >= k).mean() * 100 for k in ks]
    fig = go.Figure(go.Scatter(x=ks, y=surv, mode="lines", fill="tozeroy", line=dict(color=BLUE)))
    fig.update_layout(height=340, margin=dict(t=20, b=10), xaxis_title="일수 K", yaxis_title="생존율 (%)")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("※ 최근 출시 소재는 절단(censoring)으로 수명이 짧게 잡힘 — 최근 코호트 장기율은 과소.")

    q1, q2 = st.columns(2)
    with q1:
        st.subheader("출시월별 평균 CTR")
        cs2 = cs.copy()
        cs2["출시월"] = cs2["최초집행"].dt.to_period("M").astype(str)
        mm = cs2.dropna(subset=["CTR"]).groupby("출시월").apply(
            lambda x: (x["클릭"].sum() / x["노출"].sum() * 100) if x["노출"].sum() else 0).reset_index(name="CTR")
        fig2 = px.bar(mm, x="출시월", y="CTR", color_discrete_sequence=[BLUE])
        fig2.update_layout(height=320, margin=dict(t=20, b=10), yaxis_title="CTR (%)")
        st.plotly_chart(fig2, use_container_width=True)
    with q2:
        st.subheader("출시월별 소재 수명 분포")
        cs2["구간"] = pd.cut(cs2["수명일"], [0, 14, 29, 10**9], labels=["단기≤14", "중기15-29", "장기≥30"])
        dist = cs2.groupby(["출시월", "구간"], observed=True).size().reset_index(name="n")
        fig3 = px.bar(dist, x="출시월", y="n", color="구간", barmode="stack",
                      color_discrete_map={"단기≤14": "#fca5a5", "중기15-29": "#fde047", "장기≥30": GREEN})
        fig3.update_layout(height=320, margin=dict(t=20, b=10), yaxis_title="소재 수")
        st.plotly_chart(fig3, use_container_width=True)

# ─────────────────────────── ⑤ 캠페인 ───────────────────────────
with tabs[4]:
    st.subheader("캠페인별 성과")
    spent_c = df[df["spend"] > 0].groupby("campaign_name")["date"]
    gc = df.groupby("campaign_name")
    camp = pd.DataFrame({
        "지출": gc["spend"].sum(), "구매": gc["omni_purchase"].sum(),
        "소재수": gc["소재"].nunique(), "광고수": gc["ad_id"].nunique(),
        "최초": spent_c.min(), "최종": spent_c.max(),
    })
    camp["수명일"] = (camp["최종"] - camp["최초"]).dt.days + 1
    camp["CPA"] = (camp["지출"] / camp["구매"]).where(camp["구매"] > 0)
    camp = camp.reset_index()
    camp["최초"] = camp["최초"].dt.date
    camp["최종"] = camp["최종"].dt.date
    camp["지출"] = camp["지출"].round(0)
    camp["CPA"] = camp["CPA"].round(0)
    st.dataframe(
        camp.sort_values("지출", ascending=False),
        use_container_width=True, hide_index=True, height=460,
        column_config={"지출": st.column_config.NumberColumn("지출(₩)", format="localized"),
                       "CPA": st.column_config.NumberColumn("CPA(₩)", format="localized")})

# ─────────────────────────── ⑥ 전략 ───────────────────────────
with tabs[5]:
    st.subheader("우선순위 액션")
    st.markdown("""
1. **소재 교체·확충 (1순위)** — 메타 효율의 유일한 실질 레버. 문제는 '피로'가 아니라 **출시 품질(양산 부작용)** → 제작 방식 개선.
2. **Google 검색 증액 (2순위)** — 자사몰 전환당 +3.3대, 건당 최고인데 규모 작음(저평가). *(구글 데이터 연결 예정)*
3. **메타는 예산증액 말고 효율개선** — 포화(비용↔CVR −0.45). 소재로 CVR 회복 후 증액.
4. **🟢 증액후보 소재부터** — 소재 분석 탭에서 활성 & 저CPA 소재 = 추가 집행 여력. 잦은 on/off 금지.
5. **하지 말 것** — 단순 CPA 미달로 끄기(학습 리셋). CPA는 kill-switch 아니라 원인 색출 트리거.
""")
    st.divider()
    st.subheader("열린 과제")
    st.markdown("""
- [ ] 매출(자사몰·네이버·쿠팡) 시트 연결 → **ROAS/영업이익** 기준 분석
- [ ] Google Ads 연결 → 채널 통합 뷰
- [ ] 소재매핑 `자동` 분류 검토·병합 (시트에서 수정 시 자동 반영)
""")
