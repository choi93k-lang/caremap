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


def get_map_data(district_name):
    """구·군별 인구 및 시설 데이터를 캐시 없이 최신 DB에서 실시간으로 직접 로드합니다 (2.5ms 소요)."""
    df_pop = get_population_summary(district_name)
    df_fac = get_facilities(district_name, "all")
    return df_pop, df_fac


def get_color_by_rate(rate):
    """실제 울산 통계 기준(12%~55%)에 맞춘 고령화율 단계 색상(초록-노랑-빨강)을 반환합니다."""
    if rate >= 30.0:
        return "#D7191C"  # 30% 이상: 진한 빨간색 (초고령 심화 지역)
    elif rate >= 25.0:
        return "#FDAE61"  # 25% ~ 30%: 주황-빨간색
    elif rate >= 20.0:
        return "#FEE08B"  # 20% ~ 25%: 따뜻한 노란색 (초고령사회 진입 기준)
    elif rate >= 16.0:
        return "#A6D96A"  # 16% ~ 20%: 연한 연두색
    else:
        return "#1A9641"  # 16% 미만: 맑은 초록색 (상대적 젊은 신도심)


def create_base_map(center_lat, center_lon, zoom_level):
    """기본 타일 지도를 생성하고 마커 클러스터에 보라색 테마 스타일을 주입합니다."""
    care_map = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_level,
        tiles="OpenStreetMap"
    )
    # 마커 클러스터 숫자 뱃지가 기본 초록색이 아닌 선명한 보라색으로 표시되도록 CSS 주입
    custom_cluster_css = """
    <style>
    .marker-cluster-small, .marker-cluster-medium, .marker-cluster-large {
        background-color: rgba(156, 39, 176, 0.4) !important;
    }
    .marker-cluster-small div, .marker-cluster-medium div, .marker-cluster-large div {
        background-color: rgba(123, 31, 162, 0.85) !important;
        color: white !important;
        font-weight: bold !important;
    }
    </style>
    """
    care_map.get_root().html.add_child(folium.Element(custom_cluster_css))
    return care_map


def add_boundary_lines(care_map, geojson_data, selected_district="전체"):
    """행정동 테두리 구역선만 지도에 표시하여 항상 경계가 보이도록 합니다."""
    if not geojson_data:
        return

    # 모든 행정동 구역선을 표시하되, 선택된 구는 진하게, 다른 구는 연하게 표시
    display_features = []
    for feature in geojson_data["features"]:
        feature_copy = dict(feature)
        props = dict(feature["properties"])
        f_district = props.get("district_name") or props.get("sggnm")
        props["is_selected"] = (selected_district == "전체" or f_district == selected_district)
        feature_copy["properties"] = props
        display_features.append(feature_copy)

    boundary_geojson = {
        "type": "FeatureCollection",
        "features": display_features
    }

    def boundary_style(feature):
        is_selected = feature["properties"].get("is_selected", True)
        if is_selected:
            return {
                "fill": False,
                "color": "#333333",
                "weight": 1.5,
                "dashArray": "2, 4"  # 선택된 구: 또렷한 점선 구역선
            }
        else:
            return {
                "fill": False,
                "color": "#CCCCCC",
                "weight": 0.8,
                "dashArray": "3, 3"  # 다른 구: 옅은 점선 구역선
            }

    folium.GeoJson(
        boundary_geojson,
        name="행정동 구역선 (기본)",
        style_function=boundary_style,
        tooltip=folium.GeoJsonTooltip(
            fields=["dong_name"],
            aliases=["행정동:"],
            localize=True
        )
    ).add_to(care_map)


def add_choropleth_layer(care_map, geojson_data, df_pop, selected_district="전체"):
    """행정동별 고령화율 색상 채우기 레이어를 추가합니다. (선택된 구는 강조, 다른 구는 흐리게)"""
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

    # 모든 행정동을 포함하되, 선택 구역과 비선택 구역을 구분
    display_features = []
    for feature in geojson_data["features"]:
        feature_copy = dict(feature)
        props = dict(feature["properties"])
        f_district = props.get("district_name") or props.get("sggnm")
        is_selected = (selected_district == "전체" or f_district == selected_district)
        props["is_selected"] = is_selected

        code = str(props.get("adm_cd2", ""))
        info = pop_lookup.get(code, {"dong": props.get("dong_name", "미상"), "rate": 0, "total": 0, "elderly": 0})
        props["aging_rate"] = info["rate"]
        props["total_pop"] = info["total"]
        props["elderly_pop"] = info["elderly"]

        feature_copy["properties"] = props
        display_features.append(feature_copy)

    display_geojson = {
        "type": "FeatureCollection",
        "features": display_features
    }

    def style_function(feature):
        props = feature["properties"]
        is_selected = props.get("is_selected", True)

        if is_selected:
            # 선택된 구: 고령화율에 따른 선명한 색상 및 또렷한 테두리
            rate = props.get("aging_rate", 0)
            return {
                "fillColor": get_color_by_rate(rate),
                "color": "#222222",
                "weight": 1.8,
                "fillOpacity": 0.65
            }
        else:
            # 선택되지 않은 주변 구: 뚜렷한 미디엄 그레이로 확실하게 톤다운 (Dimming)
            return {
                "fillColor": "#757575",
                "color": "#9E9E9E",
                "weight": 0.8,
                "fillOpacity": 0.55
            }

    geojson_layer = folium.GeoJson(
        display_geojson,
        name="🎨 고령화율 색상 채우기",
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

    # 1. 병·의원 레이어 (마커 클러스터 적용으로 초고속 로딩)
    if show_hospitals:
        hospital_cluster = MarkerCluster(name="🏥 병·의원 레이어 (클러스터)")
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
            ).add_to(hospital_cluster)
        hospital_cluster.add_to(care_map)

    # 2. 경로당 레이어 (마커 클러스터 적용)
    if show_centers:
        center_cluster = MarkerCluster(name="👵 경로당 레이어 (클러스터)")
        centers = valid_fac[valid_fac["facility_type"] == "senior_center"]
        for _, row in centers.iterrows():
            tel = row['tel_number'] if row['tel_number'] else '정보없음'
            popup_text = f"<b>👵 {row['facility_name']}</b><br>주소: {row['road_address']}<br>전화: {tel}"
            folium.CircleMarker(
                location=[row["latitude"], row["longitude"]],
                radius=5,
                color="#4A148C",
                fill=True,
                fill_color="#9C27B0",
                fill_opacity=0.9,
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
    show_hospitals = st.sidebar.checkbox("🏥 병·의원 마커 표시 (파랑)", value=True)
    show_centers = st.sidebar.checkbox("👵 경로당 마커 표시 (보라)", value=True)
    show_choropleth = st.sidebar.checkbox("🎨 행정동 고령화율 단계구분도 표시", value=True)

    # 최신 데이터 실시간 로드 (캐시 지연 방지)
    df_pop, df_fac = get_map_data(selected_district)
    geojson_data = load_geojson_data()

    # 지도 중심점 계산
    center_info = DISTRICT_CENTERS.get(selected_district, DISTRICT_CENTERS["전체"])
    care_map = create_base_map(center_info[0], center_info[1], center_info[2])

    # 1. 행정동 기본 테두리 구역선 (항상 지도에 표시)
    add_boundary_lines(care_map, geojson_data, selected_district)

    # 2. 고령화율 색상 채우기 레이어 (토글 가능)
    if show_choropleth:
        add_choropleth_layer(care_map, geojson_data, df_pop, selected_district)

    # 3. 의료 및 복지 시설 마커
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
        st.warning("💡 범례: 30%+ (진한빨강) / 20~25% (노랑) / 16%미만 (초록)")

    # Streamlit에 Folium 지도 렌더링 (returned_objects=[] 로 단방향 경량 모드 활성화)
    st_folium(care_map, width="100%", height=600, returned_objects=[])


if __name__ == "__main__":
    main()

