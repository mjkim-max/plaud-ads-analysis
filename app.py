"""PLAUD 광고 성과 대시보드 (Streamlit).

Phase 1 MVP — 로컬 엑셀(캠페인 신설·생존 데이터) 기반.
Phase 2 에서 Meta/Google/매출 API → BigQuery 연결로 실시간화 예정.

근거 분석: 광고분석_종합정리.md / 광고분석_대시보드_가이드(_보강분).md
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import data_loader as dl

st.set_page_config(page_title="PLAUD 광고 성과 대시보드", page_icon="📊", layout="wide")

# ── 분석 문서에서 확정된 요약 수치 (Phase 2 에서 라이브 계산으로 대체) ──
CHANNEL_MIX = {"네이버": 42, "자사몰": 34, "쿠팡": 22, "기타": 1}
SELF_MALL_REGRESSION = {  # 자사몰 전환 1건당 판매 대수 (증감 회귀)
    "Google검색": 3.3, "메타": 0.85, "디멘드젠": 0.39,
}
META_CPA_START, META_CPA_NOW = 82_000, 157_000

st.title("📊 PLAUD 광고 성과 대시보드")
st.caption(
    "자사몰 매출 우상향이 목표. 광고는 **자사몰(34%)에만 귀인**. "
    "액션 판단은 증감상관, 구조 진단은 수준상관 기준. · 데이터: 캠페인 신설·생존(~2026-07-07)"
)

tab_names = [
    "① 개요", "② 캠페인 병렬", "③ 캠페인 생존", "④ 소재 생존",
    "⑤ 메타 효율", "⑥ 채널별", "⑦ 소재 품질", "⑧ 전략·액션",
]
tabs = st.tabs(tab_names)

# ────────────────────────────── ① 개요 ──────────────────────────────
with tabs[0]:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("메타 CPA (현재)", f"{META_CPA_NOW:,}원",
              f"{META_CPA_NOW - META_CPA_START:+,}원 vs 연초", delta_color="inverse")
    wk = dl.load_weekly_campaigns()
    latest_active = int(wk["동시활성"].iloc[-1]) if not wk.empty else 0
    c2.metric("동시활성 캠페인", f"{latest_active}개", "연초 대비 약 2배")
    c3.metric("동시활성 ↔ CPA", "+0.85", "병렬↑ = CPA↑ (학습낭비)", delta_color="off")
    surv = dl.load_campaign_survival()
    med_life = int(surv["생존일수"].median()) if not surv.empty else 0
    c4.metric("캠페인 중앙 수명", f"{med_life}일", delta_color="off")

    st.divider()
    g1, g2 = st.columns(2)
    with g1:
        st.subheader("판매 채널 구성")
        fig = go.Figure(go.Pie(
            labels=list(CHANNEL_MIX), values=list(CHANNEL_MIX.values()), hole=0.5,
            marker_colors=["#22c55e", "#2563eb", "#f59e0b", "#9ca3af"]))
        fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=320)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("도넛은 매출 **출처 비중**이지 광고 효율이 아님. 광고는 자사몰 34%에만 귀인.")
    with g2:
        st.subheader("자사몰 매출 회귀 — 전환 1건당 판매 대수")
        reg = pd.DataFrame(
            {"채널": list(SELF_MALL_REGRESSION), "판매대수": list(SELF_MALL_REGRESSION.values())})
        fig = px.bar(reg, x="판매대수", y="채널", orientation="h", text="판매대수",
                     color="채널", color_discrete_sequence=["#2563eb", "#22c55e", "#f59e0b"])
        fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=320)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("**Google검색 +3.3대**로 건당 효율 최고인데 규모가 작음 = 가장 저평가된 기회.")

# ───────────────────────────── ② 캠페인 병렬 ─────────────────────────
with tabs[1]:
    st.subheader("주별 신설 · 종료 · 동시활성")
    wk = dl.load_weekly_campaigns()
    fig = go.Figure()
    fig.add_bar(x=wk["주차"], y=wk["신설"], name="신설", marker_color="#93c5fd")
    fig.add_bar(x=wk["주차"], y=wk["종료"], name="종료", marker_color="#fca5a5")
    fig.add_scatter(x=wk["주차"], y=wk["동시활성"], name="동시활성",
                    mode="lines+markers", line=dict(color="#2563eb", width=3), yaxis="y2")
    fig.update_layout(
        barmode="group", height=420, margin=dict(t=20, b=10),
        yaxis=dict(title="신설/종료"), yaxis2=dict(title="동시활성", overlaying="y", side="right"),
        legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, use_container_width=True)
    st.info("동시활성 11 → 30개로 병렬 증설. **동시활성 ↔ CPA = +0.85** — 많이 돌릴수록 학습 낭비로 CPA 상승. "
            "CPM(자가경쟁)이 아니라 학습단계 낭비다(동시활성↔CPM 0.04).")

    st.subheader("월별 소재 수명 분포 (단 ≤14 / 중 15–29 / 장 ≥30일)")
    mt = dl.load_monthly_tiers()
    fig2 = go.Figure()
    for col, color in [("단기 ≤14일", "#fca5a5"), ("중기 15-29일", "#fde047"), ("장기 ≥30일", "#22c55e")]:
        if col in mt.columns:
            fig2.add_bar(x=mt["코호트"].astype(str), y=mt[col] * 100, name=col, marker_color=color)
    fig2.update_layout(barmode="stack", height=360, yaxis_title="비율 (%)", margin=dict(t=20, b=10),
                       legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("변곡점 = **4월(양산 시작)**. 6월 단기 75%·장기 6% — 최근 소재가 빨리 죽음. "
               "단, 최근 월은 절단으로 장기%가 과소.")

# ───────────────────────────── ③ 캠페인 생존 ─────────────────────────
with tabs[2]:
    surv = dl.load_campaign_survival()
    st.subheader("생존일수 vs CPA — 오래 산 캠페인이 효율이 좋은가")
    plot_df = surv.dropna(subset=["생존일수", "CPA(KRW)", "총지출(KRW)"])
    plot_df = plot_df[plot_df["CPA(KRW)"] > 0]
    fig = px.scatter(plot_df, x="생존일수", y="CPA(KRW)", color="상태",
                     hover_name="캠페인", size="총지출(KRW)", size_max=30,
                     color_discrete_map={"진행중": "#2563eb", "종료": "#9ca3af"})
    fig.update_layout(height=420, margin=dict(t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("장수 저CPA 히어로 / 고CPA 낭비 캠페인")
    view = surv[["캠페인", "생존일수", "상태", "총지출(KRW)", "총구매", "CPA(KRW)"]].copy()
    st.dataframe(
        view.sort_values("CPA(KRW)", na_position="last"),
        use_container_width=True, hide_index=True,
        column_config={
            "총지출(KRW)": st.column_config.NumberColumn(format="%,d"),
            "CPA(KRW)": st.column_config.NumberColumn(format="%,d"),
        })
    st.caption("정렬로 '장수+저CPA'(성숙·유지 대상) vs '단명+고CPA'(정리 대상) 식별. "
               "활성일↔CPA −0.36 / 잦은 ON/OFF↔CPA +0.23.")

# ─────────────────── ④~⑦ 소스 데이터 필요 (스텁) ───────────────────
NEED_SOURCE = {
    3: ("소재 생존", "생존곡선·수명분포. `일별-구매-링크(8).xlsx`(소재 140개) 필요."),
    4: ("메타 효율", "일/주/월 비용·CPA·CTR·CVR·CPM 시계열. `일별-구매-링크(2)/(6).xlsx` 필요."),
    5: ("채널별 상세", "13개 채널 주별 비용·전환·CPA. `일별-구매-링크(2).xlsx` 필요."),
    6: ("소재 품질·피로", "출시월별 CTR, 초기 vs 후기 CTR 매칭. `일별-구매-링크(8).xlsx` 필요."),
}
for idx, (title, need) in NEED_SOURCE.items():
    with tabs[idx]:
        st.subheader(title)
        st.warning(f"🔜 **소스 데이터 대기 중** — {need}\n\n"
                   "현재 vault엔 캠페인 신설·생존 엑셀만 있음. 주간 채널·소재 원본을 넣으면 이 탭을 채웁니다.")

# ───────────────────────────── ⑧ 전략·액션 ─────────────────────────
with tabs[7]:
    st.subheader("우선순위 액션")
    st.markdown("""
1. **소재 교체·확충 (1순위)** — 메타 효율의 유일한 실질 레버. 문제는 '피로'가 아니라 **출시 품질(양산 부작용)** → 제작 방식을 손봐야.
2. **Google 검색 증액 (2순위)** — 자사몰 전환당 +3.3대, 건당 최고인데 규모 작음(저평가).
3. **메타는 예산증액 말고 효율개선** — 포화(비용↔CVR −0.45). 소재로 CVR 회복 후 증액.
4. **디멘드젠 소액 증액 테스트** — 증감 기여 유의(+9.7대/100만원).
5. **승자 소재 성숙·유지** — 잦은 on/off 금지(ON수↔CPA +0.23).
6. **하지 말 것** — 단순 CPA 미달로 캠페인 끄기(학습 리셋 → CPA 악화). CPA는 kill-switch 아니라 원인 색출 트리거.
7. **증액 대상 아님** — PMax·GDN(자사몰 증분 근거 없음, 유지), 디젠트래픽·머니코믹스·리타게팅(축소 검토).
""")
    st.divider()
    st.subheader("열린 검증 과제")
    st.markdown("""
- [ ] ROAS/영업이익 기준 분석 (`연간 매출 분석 시작.xlsx`)
- [ ] 양산 부작용 vs 순수 소재 품질 저하 분리
- [ ] 신설 캠페인 30일+ 생존율(히어로 발굴율) 코호트 추적
- [ ] 온/오프 증분(incrementality) 테스트 — 디젠트래픽·PMax 실제 기여
""")
