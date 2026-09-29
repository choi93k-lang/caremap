import streamlit as st
from database.db_manager import get_population_summary, get_facilities

# 전체 앱의 전역 페이지 설정 (st.navigation 사용 시 메인 진입점에서 1회만 호출)
st.set_page_config(
    page_title="울산 시니어 케어맵",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)


def show_home_page():
    """메인 홈 화면 콘텐츠를 표시합니다."""
    st.title("🗺️ 울산 시니어 케어맵")
    st.subheader("고령인구 생활안전·의료복지 인프라 접근성 대시보드")
    st.markdown("""
    **울산 시니어 케어맵**은 울산광역시 내 고령인구 분포와 의료·여가 복지시설(병·의원, 경로당)의 
    지역별 공간 분포를 탐색하고 비교하는 데이터 시각화 보조도구입니다.
    """)

    # 데이터 로드
    df_pop = get_population_summary("전체")
    df_fac = get_facilities("전체", "all")

    # 상단 KPI 메트릭 카드
    total_population = df_pop["total_population"].sum()
    total_elderly = df_pop["elderly_population"].sum()
    avg_aging_rate = round((total_elderly / total_population) * 100, 2) if total_population > 0 else 0

    hospital_count = len(df_fac[df_fac["facility_type"] == "hospital"])
    senior_center_count = len(df_fac[df_fac["facility_type"] == "senior_center"])

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("총인구수", f"{total_population:,}명")
    col2.metric("65세 이상 고령인구", f"{total_elderly:,}명")
    col3.metric("울산 평균 고령화율", f"{avg_aging_rate:.2f}%")
    col4.metric("병·의원 수", f"{hospital_count:,}개소")
    col5.metric("경로당 수", f"{senior_center_count:,}개소")

    st.markdown("---")
    st.markdown("### 📌 대시보드 메뉴 안내")

    col1, col2 = st.columns(2)
    with col1:
        st.info("""
        [**1. 📊 종합 현황 (Overview) ➔**](/종합현황)
        - 구·군별 고령인구 현황 및 고령화율 비교
        - 고령화율 상위 10개 행정동 순위 확인
        - 구·군 단위 인프라 요약 통계
        """)
        st.success("""
        [**2. 🗺️ 시니어 케어 지도 (Map) ➔**](/시니어지도)
        - 행정동별 고령화율 단계구분도(Choropleth)
        - 병·의원 및 경로당 위치 마커 레이어 토글
        - 시설 밀집도 확인을 위한 마커 클러스터링
        """)

    with col2:
        st.warning("""
        [**3. ⚖️ 지역 비교 및 사분면 분석 (Comparison) ➔**](/지역비교)
        - 고령화율 vs 1천명당 시설 수 4분면 산점도
        - 상대적 인프라 관심 지역 탐색
        - 두 개 행정동 1:1 맞비교 분석
        """)
        st.info("""
        [**4. 📋 상세 정보 & 데이터 품질 (Detail & Quality) ➔**](/상세및품질)
        - 행정동별 시설 상세 목록 및 CSV 다운로드
        - 좌표 결측치 등 데이터 품질 지표 점검
        - 공공데이터 원천 출처 및 분석 한계 안내
        """)

    st.markdown("---")
    st.caption("데이터 기준: 2026년 8월 | 공공데이터포털, 행정안전부, 통계청 SGIS 기반 | 울산 시니어 케어맵 프로젝트 2팀")


# 사이드바 화면에 표시될 페이지 목록 구성 (사이드바에 명시적으로 'Home'으로 표시)
home_page = st.Page(show_home_page, title="Home", icon="🏠", default=True)
overview_page = st.Page("pages/1_종합현황.py", title="종합현황", icon="📊")
map_page = st.Page("pages/2_시니어지도.py", title="시니어지도", icon="🗺️")
compare_page = st.Page("pages/3_지역비교.py", title="지역비교", icon="⚖️")
quality_page = st.Page("pages/4_상세및품질.py", title="상세및품질", icon="📋")

pg = st.navigation([home_page, overview_page, map_page, compare_page, quality_page])
pg.run()
