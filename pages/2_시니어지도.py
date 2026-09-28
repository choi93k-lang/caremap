import os
import json
import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from database.db_manager import get_all_districts, get_facilities, get_population_summary

GEOJSON_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ulsan_dong.geojson")

# 구·군별 지도 중심 좌표
DISTRICT_CENTERS = {
    "전체": [35.538, 129.311, 11],
    "남구": [35.535, 129.315, 13],
    "중구": [35.565, 129.325, 13],
    "동구": [35.510, 129.425, 13],
    "북구": [35.610, 129.365, 12],
    "울주군": [35.510, 129.210, 11],
}


@st.cache_data
def load_geojson_data():
    """울산 행정동 GeoJSON 데이터를 메모리에 캐싱하여 로드합니다."""
    if os.path.exists(GEOJSON_PATH):
        with open(GEOJSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


@st.cache_data
def get_cached_map_data(district_name):
    """구·군별 인구 및 시설 데이터를 캐싱하여 로드합니다."""
    df_pop = get_population_summary(district_name)
    df_fac = get_facilities(district_name, "all")
    return df_pop, df_fac


def get_color_by_rate(rate):
    """고령화율 값에 따라 연속형 단계 색상을 반환합니다."""
    if rate >= 25.0:
        return "#BD0026"
    elif rate >= 20.0:
        return "#F03B20"
    elif rate >= 17.0:
        return "#FD8D3C"
    elif rate >= 14.0:
        return "#FECC5C"
    else:
        return "#FFFFB2"


def create_base_map(center_lat, center_lon, zoom_level):
    """기본 타일 지도를 생성합니다."""
    care_map = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_level,
        tiles="OpenStreetMap"
    )
    return care_map


def add_choropleth_layer(care_map, geojson_data, df_pop):
    """행정동별 고령화율 단계구분도 레이어를 추가합니다."""
    if not geojson_data:
        return

    # 행정동코드 기준 고령화율 및 동이름 딕셔너리
    pop_lookup = {}
    for _, row in df_pop.iterrows():
        code = str(row["region_code"])
        pop_lookup[code] = {
            "dong": row["dong_name"],
            "rate": row["aging_rate"],
            "total": row["total_population"],
            "elderly": row["elderly_population"]
        }

    # GeoJSON 각 폴리곤 속성에 인구 데이터 주입
    for feature in geojson_data["features"]:
        props = feature["properties"]
        code = str(props.get("adm_cd2", ""))
        info = pop_lookup.get(code, {"dong": props.get("dong_name", "미상"), "rate": 0, "total": 0, "elderly": 0})
        props["aging_rate"] = info["rate"]
        props["total_pop"] = info["total"]
        props["elderly_pop"] = info["elderly"]

    def style_function(feature):
        rate = feature["properties"].get("aging_rate", 0)
        return {
            "fillColor": get_color_by_rate(rate),
            "color": "#333333",
            "weight": 1.5,
            "fillOpacity": 0.55
        }

    geojson_layer = folium.GeoJson(
        geojson_data,
        name="행정동 고령화율 (Choropleth)",
        style_function=style_function,
        tooltip=folium.GeoJsonTooltip(
            fields=["dong_name", "aging_rate", "total_pop", "elderly_pop"],
            aliases=["행정동:", "고령화율(%):", "총인구(명):", "고령인구(명):"],
            localize=True
        )
    )
    geojson_layer.add_to(care_map)


def add_facility_markers(care_map, df_fac, show_hospitals, show_centers):
    """병·의원 및 경로당 마커를 가벼운 툴팁과 팝업으로 지도에 추가합니다."""
    # 유효한 좌표만 필터링
    valid_fac = df_fac[df_fac["is_coord_valid"] == 1].dropna(subset=["latitude", "longitude"])

    # 1. 병·의원 레이어
    if show_hospitals:
        hospital_group = folium.FeatureGroup(name="🏥 병·의원 레이어")
        hospitals = valid_fac[valid_fac["facility_type"] == "hospital"]
        for _, row in hospitals.iterrows():
            tel = row['tel_number'] if row['tel_number'] else '정보없음'
            popup_text = f"<b>🏥 {row['facility_name']}</b><br>주소: {row['road_address']}<br>전화: {tel}"
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=5,
                color="#1F77B4",
                fill=True,
                fill_color="#1F77B4",
                fill_opacity=0.85,
                tooltip=f"🏥 {row['facility_name']}",
                popup=folium.Popup(popup_text, max_width=240)
            ).add_to(hospital_group)
        hospital_group.add_to(care_map)

    # 2. 경로당 레이어 (마커 클러스터 적용)
    if show_centers:
        center_cluster = MarkerCluster(name="👵 경로당 레이어 (클러스터)")
        centers = valid_fac[valid_fac["facility_type"] == "senior_center"]
        for _, row in centers.iterrows():
            tel = row['tel_number'] if row['tel_number'] else '정보없음'
            popup_text = f"<b>👵 {row['facility_name']}</b><br>주소: {row['road_address']}<br>전화: {tel}"
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=4,
                color="#2ECC71",
                fill=True,
                fill_color="#2ECC71",
                fill_opacity=0.85,
                tooltip=f"👵 {row['facility_name']}",
                popup=folium.Popup(popup_text, max_width=240)
            ).add_to(center_cluster)
        center_cluster.add_to(care_map)


def main():
    st.title("🗺️ 울산 시니어 케어 인터랙티브 지도")
    st.caption("고령인구 비율 단계구분도와 의료/복지 시설의 공간 분포를 한 지도에서 탐색합니다.")

    # 사이드바 설정
    st.sidebar.header("🔍 지도 레이어 및 지역 필터")
    districts = get_all_districts()
    selected_district = st.sidebar.selectbox("구·군 선택", districts, index=0)

    st.sidebar.markdown("---")
    st.sidebar.subheader("시설 표시 토글")
    show_hospitals = st.sidebar.checkbox("🏥 병·의원 마커 표시", value=True)
    show_centers = st.sidebar.checkbox("👵 경로당 마커 표시", value=True)
    show_choropleth = st.sidebar.checkbox("🎨 행정동 고령화율 단계구분도 표시", value=True)

    # 캐싱된 데이터 로드
    df_pop, df_fac = get_cached_map_data(selected_district)
    geojson_data = load_geojson_data()

    # 지도 중심점 계산
    center_info = DISTRICT_CENTERS.get(selected_district, DISTRICT_CENTERS["전체"])
    care_map = create_base_map(center_info[0], center_info[1], center_info[2])

    # 레이어 추가
    if show_choropleth:
        add_choropleth_layer(care_map, geojson_data, df_pop)

    add_facility_markers(care_map, df_fac, show_hospitals, show_centers)

    # 레이어 컨트롤 추가
    folium.LayerControl(position="topright").add_to(care_map)

    # 상단 요약 배지
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info(f"📍 현재 지역: **{selected_district}**")
    with col2:
        valid_count = len(df_fac[df_fac['is_coord_valid'] == 1])
        st.success(f"📌 지도 표시 시설: **{valid_count:,}개소**")
    with col3:
        st.warning("💡 범례: 고령화율 25%+ (진한빨강) ~ 14%미만 (연노랑)")

    # Streamlit에 Folium 지도 렌더링 (returned_objects=[] 로 단방향 경량 모드 활성화)
    st_folium(care_map, width="100%", height=600, returned_objects=[])


if __name__ == "__main__":
    main()

