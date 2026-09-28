import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from database.db_manager import get_region_comparison_data, get_all_districts

def render_scatter_section(df_comp):
    """사분면 산점도를 렌더링하고 탐색 가이드를 제공합니다."""
    st.subheader("🔍 고령화율 vs 인구 대비 시설 공급 사분면 분석")
    st.caption("고령화 비율과 65세 이상 인구 1,000명당 시설 수를 비교하여 상대적인 공급 수준을 탐색합니다.")

    # Y축 지표 선택 라디오 버튼
    col1, col2 = st.columns([1, 3])
    with col1:
        metric_choice = st.radio(
            "비교할 시설 지표 선택",
            ["병·의원 (1천명당)", "경로당 (1천명당)", "전체 시설 (1천명당)"],
            index=0
        )

    # 선택에 따른 컬럼 매핑
    if metric_choice == "병·의원 (1천명당)":
        y_col = "hospitals_per_1k"
        y_label = "고령인구 1천명당 병·의원 수 (개소)"
        count_col = "hospital_count"
    elif metric_choice == "경로당 (1천명당)":
        y_col = "centers_per_1k"
        y_label = "고령인구 1천명당 경로당 수 (개소)"
        count_col = "senior_center_count"
    else:
        df_comp["total_facilities_per_1k"] = df_comp["hospitals_per_1k"] + df_comp["centers_per_1k"]
        y_col = "total_facilities_per_1k"
        y_label = "고령인구 1천명당 전체 시설 수 (개소)"
        count_col = "total_facility_count"

    # 중앙값(Median) 기준선 계산
    x_median = df_comp["aging_rate"].median()
    y_median = df_comp[y_col].median()

    # Plotly 산점도 생성
    fig = px.scatter(
        df_comp,
        x="aging_rate",
        y=y_col,
        color="district_name",
        hover_name="dong_name",
        hover_data={
            "district_name": True,
            "aging_rate": ":.2f%",
            "elderly_population": ":,명",
            count_col: ":,개소",
            y_col: ":.2f개"
        },
        labels={
            "aging_rate": "고령화율 (%)",
            y_col: y_label,
            "district_name": "구·군"
        },
        title=f"고령화율 vs {y_label} 산점도 (기준선: 울산 중앙값)"
    )

    # 4분면 기준선 (중앙값) 추가
    fig.add_vline(x=x_median, line_dash="dash", line_color="gray", annotation_text=f"고령화율 중앙값 ({x_median:.1f}%)")
    fig.add_hline(y=y_median, line_dash="dash", line_color="gray", annotation_text=f"시설수 중앙값 ({y_median:.1f}개)")

    fig.update_traces(marker=dict(size=12, opacity=0.85, line=dict(width=1, color="DarkSlateGrey")))
    fig.update_layout(template="plotly_white", height=520)

    st.plotly_chart(fig, use_container_width=True)

    # 사분면 해석 가이드
    with st.expander("💡 사분면 해석 방법 및 정책적 시사점 보기"):
        st.markdown(f"""
        - **제4사분면 (우측 하단 - 관심 필요 지역)**:
          - 고령화율은 중앙값({x_median:.1f}%)보다 **높으나**, 인구 1천명당 시설 수는 중앙값({y_median:.1f}개)보다 **낮은** 지역입니다.
          - 고령 인구 밀도에 비해 시설 공급 확충이나 이동 지원 서비스 검토가 우선될 수 있습니다.
        - **제1사분면 (우측 상단 - 시설 충족 고령 지역)**:
          - 고령화율도 높고, 인구 대비 시설 공급도 비교적 충분한 지역입니다.
        - **제2사분면 (좌측 상단)**:
          - 고령화율은 상대적으로 낮으나 인구 대비 시설 수가 넉넉한 지역입니다.
        - **제3사분면 (좌측 하단 - 청장년 밀집 신도심)**:
          - 고령화율과 시설 지표가 모두 낮은 신도심 또는 주거 개발 지역입니다.
        """)


def render_dong_comparison_section(df_comp):
    """두 개의 행정동을 선택해 1:1로 비교하는 섹션을 렌더링합니다."""
    st.markdown("---")
    st.subheader("👥 행정동 1:1 맞비교 분석")
    st.caption("비교하고 싶은 두 행정동을 선택하여 인구 구성과 인프라 수준을 상세히 비교합니다.")

    # 행정동 선택 레이블 생성 (예: 남구 신정1동)
    df_comp["full_label"] = df_comp["district_name"] + " " + df_comp["dong_name"]
    dong_list = df_comp["full_label"].tolist()

    col1, col2 = st.columns(2)
    with col1:
        dong_a = st.selectbox("비교 지역 A 선택", dong_list, index=0)
    with col2:
        # 기본값으로 두 번째 동 선택
        dong_b = st.selectbox("비교 지역 B 선택", dong_list, index=min(1, len(dong_list) - 1))

    data_a = df_comp[df_comp["full_label"] == dong_a].iloc[0]
    data_b = df_comp[df_comp["full_label"] == dong_b].iloc[0]

    # 비교 메트릭 카드 2열 배치
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"### 📍 {dong_a}")
        sub1, sub2, sub3 = st.columns(3)
        sub1.metric("총인구", f"{int(data_a['total_population']):,}명")
        sub2.metric("고령인구", f"{int(data_a['elderly_population']):,}명")
        sub3.metric("고령화율", f"{data_a['aging_rate']:.2f}%")

        sub4, sub5 = st.columns(2)
        sub4.metric("병·의원 수 (1천명당)", f"{int(data_a['hospital_count'])}개 ({data_a['hospitals_per_1k']:.2f}개)")
        sub5.metric("경로당 수 (1천명당)", f"{int(data_a['senior_center_count'])}개 ({data_a['centers_per_1k']:.2f}개)")

    with c2:
        st.success(f"### 📍 {dong_b}")
        sub1, sub2, sub3 = st.columns(3)
        sub1.metric("총인구", f"{int(data_b['total_population']):,}명")
        sub2.metric("고령인구", f"{int(data_b['elderly_population']):,}명")
        sub3.metric("고령화율", f"{data_b['aging_rate']:.2f}%")

        sub4, sub5 = st.columns(2)
        sub4.metric("병·의원 수 (1천명당)", f"{int(data_b['hospital_count'])}개 ({data_b['hospitals_per_1k']:.2f}개)")
        sub5.metric("경로당 수 (1천명당)", f"{int(data_b['senior_center_count'])}개 ({data_b['centers_per_1k']:.2f}개)")

    # 막대 비교 차트
    categories = ["고령화율 (%)", "1천명당 병원수", "1천명당 경로당수"]
    values_a = [data_a["aging_rate"], data_a["hospitals_per_1k"], data_a["centers_per_1k"]]
    values_b = [data_b["aging_rate"], data_b["hospitals_per_1k"], data_b["centers_per_1k"]]

    fig_compare = go.Figure(data=[
        go.Bar(name=dong_a, x=categories, y=values_a, marker_color="#3498DB", text=[f"{v:.1f}" for v in values_a], textposition="auto"),
        go.Bar(name=dong_b, x=categories, y=values_b, marker_color="#2ECC71", text=[f"{v:.1f}" for v in values_b], textposition="auto")
    ])
    fig_compare.update_layout(barmode="group", title="두 지역 핵심 지표 시각적 비교", template="plotly_white", height=380)
    st.plotly_chart(fig_compare, use_container_width=True)


def main():
    st.title("⚖️ 지역 비교 및 사분면 분석")
    df_comp = get_region_comparison_data()

    render_scatter_section(df_comp)
    render_dong_comparison_section(df_comp)


if __name__ == "__main__":
    main()

