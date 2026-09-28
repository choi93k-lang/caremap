import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from database.db_manager import (
    get_all_districts,
    get_population_summary,
    get_facilities,
    get_region_comparison_data
)

def render_sidebar():
    """사이드바 필터를 렌더링하고 선택된 구·군 이름을 반환합니다."""
    st.sidebar.header("🔍 검색 및 필터")
    st.sidebar.selectbox("기준연월", ["2026년 08월 (최신)"], index=0)
    districts = get_all_districts()
    selected_district = st.sidebar.selectbox("구·군 선택", districts, index=0)
    return selected_district

def render_kpi_cards(df_pop, df_fac, selected_district):
    """선택된 지역의 핵심 KPI 카드 5개를 렌더링합니다."""
    total_population = int(df_pop["total_population"].sum())
    elderly_population = int(df_pop["elderly_population"].sum())
    aging_rate = round((elderly_population / total_population) * 100, 2) if total_population > 0 else 0

    hospital_count = len(df_fac[df_fac["facility_type"] == "hospital"])
    senior_center_count = len(df_fac[df_fac["facility_type"] == "senior_center"])

    st.subheader(f"📌 [{selected_district}] 핵심 요약 지표")
    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("총인구수", f"{total_population:,}명")
    col2.metric("고령인구(65세+)", f"{elderly_population:,}명")
    col3.metric("고령화율", f"{aging_rate:.2f}%")
    col4.metric("병·의원 수", f"{hospital_count:,}개소")
    col5.metric("경로당 수", f"{senior_center_count:,}개소")

def render_district_bar_chart(df_comp):
    """구·군별 고령인구와 고령화율을 비교하는 막대 차트를 렌더링합니다."""
    district_summary = df_comp.groupby("district_name").agg({
        "total_population": "sum",
        "elderly_population": "sum",
        "hospital_count": "sum",
        "senior_center_count": "sum"
    }).reset_index()

    district_summary["aging_rate"] = round(
        (district_summary["elderly_population"] / district_summary["total_population"]) * 100, 2
    )

    fig = go.Figure()
    # 65세 이상 고령인구 (좌측 축 막대)
    fig.add_trace(go.Bar(
        x=district_summary["district_name"],
        y=district_summary["elderly_population"],
        name="고령인구수 (명)",
        marker_color="#4A90E2"
    ))
    # 고령화율 (우측 축 꺾은선)
    fig.add_trace(go.Scatter(
        x=district_summary["district_name"],
        y=district_summary["aging_rate"],
        name="고령화율 (%)",
        yaxis="y2",
        mode="lines+markers+text",
        text=district_summary["aging_rate"].apply(lambda v: f"{v}%"),
        textposition="top center",
        marker=dict(size=8, color="#E94E77"),
        line=dict(width=3, color="#E94E77")
    ))

    fig.update_layout(
        title="구·군별 고령인구수 및 고령화율 비교",
        xaxis=dict(title="구·군"),
        yaxis=dict(title="고령인구수 (명)"),
        yaxis2=dict(
            title="고령화율 (%)",
            overlaying="y",
            side="right",
            range=[0, max(district_summary["aging_rate"]) + 10]
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white"
    )
    return fig

def render_top_aging_dongs_chart(df_pop):
    """고령화율 상위 10개 행정동을 표시하는 수평 막대 차트를 렌더링합니다."""
    top_10 = df_pop.sort_values(by="aging_rate", ascending=True).tail(10)
    top_10["label"] = top_10["district_name"] + " " + top_10["dong_name"]

    fig = px.bar(
        top_10,
        x="aging_rate",
        y="label",
        orientation="h",
        text="aging_rate",
        title="고령화율 상위 10개 행정동",
        labels={"aging_rate": "고령화율 (%)", "label": "행정동"},
        color="aging_rate",
        color_continuous_scale="Reds"
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig.update_layout(template="plotly_white", coloraxis_showscale=False)
    return fig

def render_district_summary_table(df_comp):
    """구·군별 인구 및 인프라 공급 수준 요약 테이블을 렌더링합니다."""
    st.subheader("📋 구·군별 종합 집계 현황")
    summary = df_comp.groupby("district_name").agg({
        "total_population": "sum",
        "elderly_population": "sum",
        "hospital_count": "sum",
        "senior_center_count": "sum"
    }).reset_index()

    summary["고령화율(%)"] = round((summary["elderly_population"] / summary["total_population"]) * 100, 2)
    summary["1천명당 병원수"] = round((summary["hospital_count"] / summary["elderly_population"]) * 1000, 2)
    summary["1천명당 경로당수"] = round((summary["senior_center_count"] / summary["elderly_population"]) * 1000, 2)

    summary.rename(columns={
        "district_name": "구·군",
        "total_population": "총인구",
        "elderly_population": "고령인구",
        "hospital_count": "병·의원 수",
        "senior_center_count": "경로당 수"
    }, inplace=True)

    st.dataframe(
        summary.style.format({
            "총인구": "{:,}명",
            "고령인구": "{:,}명",
            "병·의원 수": "{:,}개소",
            "경로당 수": "{:,}개소",
            "고령화율(%)": "{:.2f}%",
            "1천명당 병원수": "{:.2f}개",
            "1천명당 경로당수": "{:.2f}개"
        }),
        use_container_width=True
    )

def main():
    st.title("📊 울산 고령화 및 인프라 종합 현황")
    st.caption("울산광역시 전체 및 구·군별 고령인구와 시설 분포 현황을 한눈에 파악합니다.")

    selected_district = render_sidebar()

    # 데이터 로드
    df_pop = get_population_summary(selected_district)
    df_fac = get_facilities(selected_district, "all")
    df_comp = get_region_comparison_data()

    # KPI 지표 카드
    render_kpi_cards(df_pop, df_fac, selected_district)
    st.markdown("---")

    # 차트 섹션
    col1, col2 = st.columns(2)
    with col1:
        fig_bar = render_district_bar_chart(df_comp)
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        fig_top = render_top_aging_dongs_chart(df_pop)
        st.plotly_chart(fig_top, use_container_width=True)

    st.markdown("---")
    # 집계 테이블
    render_district_summary_table(df_comp)

if __name__ == "__main__":
    main()

