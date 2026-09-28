import streamlit as st
import pandas as pd
from database.db_manager import (
    get_all_districts,
    get_population_summary,
    get_facilities,
    get_db_connection
)

st.set_page_config(page_title="상세 정보 및 데이터 품질 - 울산 시니어 케어맵", page_icon="📋", layout="wide")

def render_dong_profile(selected_district):
    """선택된 구·군 및 행정동의 상세 정보와 시설 목록을 표시합니다."""
    st.subheader("🏘️ 행정동별 세부 시설 프로필")

    df_pop = get_population_summary(selected_district)
    dong_names = df_pop["dong_name"].tolist()

    selected_dong = st.selectbox("조회할 행정동 선택", dong_names, index=0)

    # 해당 동의 인구 정보 추출
    dong_pop = df_pop[df_pop["dong_name"] == selected_dong].iloc[0]

    # 해당 동의 시설 목록 조회
    connection = get_db_connection()
    query = """
        SELECT 
            f.facility_name AS '시설명',
            CASE WHEN f.facility_type = 'hospital' THEN '🏥 병·의원' ELSE '👵 경로당' END AS '구분',
            f.road_address AS '도로명주소',
            f.tel_number AS '전화번호',
            CASE WHEN f.is_coord_valid = 1 THEN '정상' ELSE '좌표누락' END AS '좌표상태'
        FROM facility f
        JOIN region r ON f.region_code = r.region_code
        WHERE r.dong_name = ?
        ORDER BY f.facility_type, f.facility_name
    """
    df_facility = pd.read_sql_query(query, connection, params=(selected_dong,))
    connection.close()

    # 인구 요약 카드
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총인구", f"{dong_pop['total_population']:,}명")
    col2.metric("고령인구", f"{dong_pop['elderly_population']:,}명")
    col3.metric("고령화율", f"{dong_pop['aging_rate']:.2f}%")
    col4.metric("등록 시설 수", f"{len(df_facility):,}개소")

    st.markdown("##### 📍 시설 목록")
    st.dataframe(df_facility, use_container_width=True)

    # CSV 다운로드 버튼
    csv_data = df_facility.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label=f"📥 {selected_dong} 시설 목록 CSV 다운로드",
        data=csv_data,
        file_name=f"{selected_dong}_시설목록.csv",
        mime="text/csv"
    )

def render_data_quality_section():
    """데이터 품질(좌표 결측치 등) 현황을 분석하여 표시합니다."""
    st.markdown("---")
    st.subheader("🛡️ 데이터 품질 및 결측치 현황")

    connection = get_db_connection()
    df_fac_all = pd.read_sql_query("SELECT * FROM facility", connection)
    connection.close()

    total_count = len(df_fac_all)
    valid_count = len(df_fac_all[df_fac_all["is_coord_valid"] == 1])
    missing_count = total_count - valid_count
    missing_rate = round((missing_count / total_count) * 100, 2) if total_count > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("전체 적재 시설 수", f"{total_count:,}건")
    col2.metric("정상 좌표 매핑 건수", f"{valid_count:,}건", delta=f"{100-missing_rate:.1f}% 유효")
    col3.metric("위·경도 결측 건수", f"{missing_count:,}건", delta=f"-{missing_rate:.2f}% 결측", delta_color="inverse")

    if missing_count > 0:
        with st.expander(f"⚠️ 좌표 결측 시설 목록 확인 ({missing_count}건)"):
            st.caption("아래 시설들은 주소 정제 과정에서 좌표 변환이 실패하여 지도 화면에서는 제외되었습니다.")
            missing_df = df_fac_all[df_fac_all["is_coord_valid"] == 0][["facility_name", "facility_type", "road_address", "tel_number"]]
            st.dataframe(missing_df, use_container_width=True)

def render_data_sources_and_limitations():
    """데이터 출처 및 라이선스, 분석상 한계점을 안내합니다."""
    st.markdown("---")
    st.subheader("📚 공공데이터 원천 출처 및 분석 한계")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **공공데이터 출처 및 기준일**
        - **고령 인구통계**: 행정안전부 주민등록 인구통계 (기준: 2026년 08월)
        - **경로당 현황**: 공공데이터포털 전국마을회관및경로당표준데이터 (보건복지부, 기준: 2026년 06월)
        - **병·의원 정보**: 국립중앙의료원 전국 병·의원 찾기 서비스 (기준: 2026년 08월)
        - **행정구역 경계**: 통계청 SGIS 행정구역 경계 WGS84 GeoJSON
        """)

    with col2:
        st.warning("""
        **분석 및 해석상의 한계점 안내**
        1. **단순 수량 지표의 한계**: 시설 '개수'는 실제 병상 수, 면적, 진료 품질, 서비스 수용 용량을 직접 대변하지 않습니다.
        2. **접근 거리 미반영**: 행정동 경계 내 존재 여부만 집계하였으므로 실제 도보 또는 대중교통 이동 소요 시간과는 차이가 있을 수 있습니다.
        3. **보조 도구 목적**: 본 대시보드는 행정동별 인프라 상대 수준을 신속히 파악하기 위한 기초 탐색 도구이며, 정책 우선순위를 직접 결정하는 절대적 점수가 아닙니다.
        """)

def main():
    st.title("📋 상세 정보 및 데이터 품질")
    st.caption("개별 행정동의 시설 정보 확인, 데이터 품질 관리 지표 및 데이터 원천 출처를 점검합니다.")

    # 사이드바에서 구·군 필터
    st.sidebar.header("🔍 지역 선택")
    districts = [d for d in get_all_districts() if d != "전체"]
    selected_district = st.sidebar.selectbox("구·군 선택", districts, index=1 if "남구" in districts else 0)

    render_dong_profile(selected_district)
    render_data_quality_section()
    render_data_sources_and_limitations()

if __name__ == "__main__":
    main()
