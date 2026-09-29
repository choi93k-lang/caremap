import os
import sys

# 프로젝트 루트 디렉터리 경로 설정 (어느 위치에서 실행해도 안전하도록 기준 경로를 잡음)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(BASE_DIR)

import re
import random
import sqlite3
import pandas as pd
from database.db_manager import get_db_connection, create_tables

# 재현성을 위한 시드 고정
random.seed(42)

# 울산 구·군별 행정동 마스터 목록 및 기준 좌표 (중심점)
DISTRICT_DONGS = {
    "남구": [
        ("3114051000", "신정1동", 35.541, 129.305),
        ("3114052000", "신정2동", 35.535, 129.309),
        ("3114053000", "신정3동", 35.545, 129.314),
        ("3114054000", "신정4동", 35.533, 129.318),
        ("3114055000", "신정5동", 35.542, 129.322),
        ("3114056000", "달동", 35.538, 129.330),
        ("3114057000", "삼산동", 35.539, 129.342),
        ("3114058500", "삼호동", 35.551, 129.278),
        ("3114059500", "무거동", 35.546, 129.260),
        ("3114060000", "옥동", 35.528, 129.288),
        ("3114062500", "대현동", 35.521, 129.334),
        ("3114063500", "수암동", 35.526, 129.324),
        ("3114064000", "선암동", 35.512, 129.345),
        ("3114067000", "야음장생포동", 35.518, 129.362),
    ],
    "중구": [
        ("3111051000", "학성동", 35.558, 129.335),
        ("3111052000", "반구1동", 35.560, 129.345),
        ("3111053000", "반구2동", 35.565, 129.348),
        ("3111054000", "복산1동", 35.568, 129.330),
        ("3111055000", "복산2동", 35.572, 129.328),
        ("3111056000", "북정동", 35.565, 129.322),
        ("3111057000", "옥교동", 35.555, 129.324),
        ("3111058000", "성남동", 35.554, 129.318),
        ("3111059000", "우정동", 35.558, 129.308),
        ("3111060000", "태화동", 35.554, 129.293),
        ("3111061000", "다운동", 35.566, 129.278),
        ("3111062000", "병영1동", 35.574, 129.345),
        ("3111063000", "병영2동", 35.580, 129.352),
        ("3111064000", "약사동", 35.578, 129.336),
    ],
    "동구": [
        ("3117051000", "방어동", 35.485, 129.418),
        ("3117052000", "일산동", 35.498, 129.428),
        ("3117053000", "화정동", 35.495, 129.416),
        ("3117054000", "대송동", 35.506, 129.418),
        ("3117055000", "전하1동", 35.515, 129.428),
        ("3117056000", "전하2동", 35.522, 129.432),
        ("3117057000", "남목1동", 35.534, 129.435),
        ("3117058000", "남목2동", 35.538, 129.442),
        ("3117059000", "남목3동", 35.545, 129.438),
    ],
    "북구": [
        ("3120051000", "농소1동", 35.632, 129.354),
        ("3120052000", "농소2동", 35.651, 129.352),
        ("3120053000", "농소3동", 35.660, 129.345),
        ("3120054000", "강동동", 35.635, 129.438),
        ("3120055000", "효문동", 35.582, 129.368),
        ("3120056000", "송정동", 35.602, 129.362),
        ("3120057000", "양정동", 35.568, 129.385),
        ("3120058000", "염포동", 35.552, 129.395),
    ],
    "울주군": [
        ("3171025000", "온산읍", 35.438, 129.345),
        ("3171025300", "언양읍", 35.568, 129.124),
        ("3171025600", "온양읍", 35.412, 129.284),
        ("3171025900", "범서읍", 35.572, 129.238),
        ("3171026000", "청량읍", 35.495, 129.312),
        ("3171026300", "삼남읍", 35.538, 129.138),
        ("3171031000", "서생면", 35.372, 129.332),
        ("3171032000", "웅촌면", 35.448, 129.224),
        ("3171033000", "두동면", 35.624, 129.182),
        ("3171034000", "두서면", 35.672, 129.155),
        ("3171035000", "상북면", 35.588, 129.068),
        ("3171036000", "삼동면", 35.492, 129.145),
    ]
}


def clear_existing_data(connection):
    """기존 테이블의 모든 데이터를 삭제합니다."""
    cursor = connection.cursor()
    cursor.execute("DELETE FROM facility")
    cursor.execute("DELETE FROM population")
    cursor.execute("DELETE FROM region")
    cursor.execute("DELETE FROM source")
    connection.commit()


def insert_sources(connection):
    """공공데이터 출처 정보를 데이터베이스에 등록합니다."""
    sources = [
        ("행정안전부 주민등록 인구통계", "행정안전부", "https://jumin.mois.go.kr/etcStatOldAge.do", "2026-08"),
        ("전국마을회관및경로당표준데이터", "보건복지부 / 공공데이터포털", "https://www.data.go.kr/data/15114136/standard.do", "2026-06"),
        ("국립중앙의료원 전국 병·의원 찾기 서비스", "국립중앙의료원 / 공공데이터포털", "https://www.data.go.kr/data/15000736/openapi.do", "2026-08"),
        ("울산광역시 행정구역 경계 (GeoJSON)", "통계청 SGIS", "https://sgis.kostat.go.kr", "2026-01")
    ]
    cursor = connection.cursor()
    cursor.executemany("""
        INSERT INTO source (data_name, provider, url, base_date)
        VALUES (?, ?, ?, ?)
    """, sources)
    connection.commit()


def load_namgu_real_population():
    """실제 다운로드받은 남구 인구 통계 CSV 파일을 읽어 딕셔너리로 반환합니다."""
    csv_path = os.path.join(BASE_DIR, "data", "raw", "ulsan_namgu_population.csv")
    pop_map = {}
    if not os.path.exists(csv_path):
        return pop_map

    try:
        df = pd.read_csv(csv_path, encoding="cp949")
        for _, row in df.iterrows():
            region_str = str(row.iloc[0])
            # 예: "울산광역시 남구 신정1동(3114051000)"
            code_match = re.search(r"\((\d+)\)", region_str)
            if code_match:
                code = code_match.group(1)
                # 콤마 제거 후 정수 변환
                total_pop = int(str(row.iloc[1]).replace(",", ""))
                male_pop = int(str(row.iloc[2]).replace(",", ""))
                female_pop = int(str(row.iloc[3]).replace(",", ""))
                elderly_total = int(str(row.iloc[4]).replace(",", ""))
                elderly_male = int(str(row.iloc[5]).replace(",", ""))
                elderly_female = int(str(row.iloc[6]).replace(",", ""))

                pop_map[code] = {
                    "total": total_pop,
                    "male": male_pop,
                    "female": female_pop,
                    "elderly_total": elderly_total,
                    "elderly_male": elderly_male,
                    "elderly_female": elderly_female,
                }
    except Exception as e:
        print(f"남구 인구 CSV 로드 중 참고: {e}")

    return pop_map


def insert_regions_and_populations(connection):
    """5개 구·군의 행정동과 인구 통계를 DB에 삽입합니다."""
    cursor = connection.cursor()
    real_namgu_pop = load_namgu_real_population()

    for district_name, dongs in DISTRICT_DONGS.items():
        for code, dong_name, center_lat, center_lon in dongs:
            # 1. region 삽입
            cursor.execute("""
                INSERT INTO region (region_code, district_name, dong_name)
                VALUES (?, ?, ?)
            """, (code, district_name, dong_name))

            # 2. population 데이터 산출
            if district_name == "남구" and code in real_namgu_pop:
                # 실제 데이터 사용
                info = real_namgu_pop[code]
                total_pop = info["total"]
                elderly_pop = info["elderly_total"]
                elderly_m = info["elderly_male"]
                elderly_f = info["elderly_female"]
            else:
                # 현실적인 모의 인구 통계 생성
                if district_name == "울주군":
                    total_pop = random.randint(8000, 28000)
                    aging_ratio = random.uniform(0.22, 0.32)  # 농어촌 높은 고령화율
                elif district_name in ["북구", "동구"]:
                    total_pop = random.randint(15000, 38000)
                    aging_ratio = random.uniform(0.13, 0.20)  # 산업단지 상대적 젊은 층
                else:  # 중구
                    total_pop = random.randint(12000, 26000)
                    aging_ratio = random.uniform(0.19, 0.26)  # 구도심 고령화율

                elderly_pop = int(total_pop * aging_ratio)
                elderly_m = int(elderly_pop * 0.45)
                elderly_f = elderly_pop - elderly_m

            aging_rate = round((elderly_pop / total_pop) * 100, 2) if total_pop > 0 else 0.0

            cursor.execute("""
                INSERT INTO population (
                    region_code, base_year_month, total_population, 
                    elderly_population, elderly_male, elderly_female, aging_rate
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (code, "2026-08", total_pop, elderly_pop, elderly_m, elderly_f, aging_rate))

    connection.commit()


def insert_facilities(connection):
    """경로당(실제 남구 133개 + 타 구 모의 데이터) 및 병·의원 시설을 생성하여 삽입합니다."""
    cursor = connection.cursor()

    # 1. 실제 남구 경로당 데이터 로드 시도
    namgu_senior_csv = os.path.join(BASE_DIR, "data", "raw", "ulsan_namgu_senior_center.csv")
    namgu_loaded = False

    if os.path.exists(namgu_senior_csv):
        try:
            df_senior = pd.read_csv(namgu_senior_csv, encoding="utf-8")
            # 남구 행정동 코드 매핑용
            namgu_dongs = DISTRICT_DONGS["남구"]

            for _, row in df_senior.iterrows():
                facility_name = str(row["시설명"])
                road_addr = str(row.get("소재지도로명주소", ""))
                lat = float(row["위도"]) if pd.notnull(row["위도"]) else None
                lon = float(row["경도"]) if pd.notnull(row["경도"]) else None
                tel = str(row.get("전화번호", ""))

                # 주소에서 행정동 추정
                matched_code = namgu_dongs[0][0]  # 기본값 신정1동
                for code, dname, _, _ in namgu_dongs:
                    if dname in road_addr or dname in facility_name:
                        matched_code = code
                        break

                is_coord_valid = 1 if (lat is not None and lon is not None) else 0

                cursor.execute("""
                    INSERT INTO facility (
                        region_code, facility_type, facility_name, 
                        road_address, latitude, longitude, tel_number, is_coord_valid
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (matched_code, "senior_center", facility_name, road_addr, lat, lon, tel, is_coord_valid))

            namgu_loaded = True
            print(f"남구 실제 경로당 {len(df_senior)}개 적재 완료")
        except Exception as e:
            print(f"남구 경로당 파일 적재 참고: {e}")

    # 2. 병원 이름 및 진료과 템플릿
    hospital_names = [
        "바른내과의원", "연세정형외과", "속편한내과의원", "울산성모의원", "한마음가정의학과의원",
        "참조은이비인후과", "중앙통증의학과의원", "굿모닝요양병원", "울산시티의원", "행복재활의학과",
        "보람신경외과의원", "온누리마취통증의학과", "밝은안과의원", "다나마취통증의학과", "울산효사랑요양병원"
    ]

    # 각 구·군 및 행정동별로 병의원과 타 구 경로당 생성
    for district_name, dongs in DISTRICT_DONGS.items():
        for code, dong_name, center_lat, center_lon in dongs:
            # (1) 병·의원 생성 (행정동당 3~8개)
            num_hospitals = random.randint(3, 8)
            for i in range(num_hospitals):
                h_name = f"{dong_name} {random.choice(hospital_names)}"
                # 중심 좌표 근처에 랜덤 산포 (+- 0.008도, 약 800m 내외)
                h_lat = round(center_lat + random.uniform(-0.006, 0.006), 6)
                h_lon = round(center_lon + random.uniform(-0.006, 0.006), 6)
                h_addr = f"울산광역시 {district_name} {dong_name} 번영로 {random.randint(10, 300)}"
                tel = f"052-{random.randint(200, 299)}-{random.randint(1000, 9999)}"

                # 테스트용 좌표 결측치 일부 생성 (전체 중 2% 정도)
                is_valid = 1
                if random.random() < 0.02:
                    h_lat, h_lon = None, None
                    is_valid = 0

                cursor.execute("""
                    INSERT INTO facility (
                        region_code, facility_type, facility_name, 
                        road_address, latitude, longitude, tel_number, is_coord_valid
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (code, "hospital", h_name, h_addr, h_lat, h_lon, tel, is_valid))

            # (2) 남구가 아닌 구·군의 경로당 생성 (행정동당 3~7개)
            if district_name != "남구" or not namgu_loaded:
                num_centers = random.randint(3, 7)
                for j in range(num_centers):
                    c_name = f"{dong_name} 제{j+1}경로당"
                    c_lat = round(center_lat + random.uniform(-0.007, 0.007), 6)
                    c_lon = round(center_lon + random.uniform(-0.007, 0.007), 6)
                    c_addr = f"울산광역시 {district_name} {dong_name} 마을길 {random.randint(5, 120)}"
                    tel = f"052-{random.randint(210, 289)}-{random.randint(1000, 9999)}"

                    cursor.execute("""
                        INSERT INTO facility (
                            region_code, facility_type, facility_name, 
                            road_address, latitude, longitude, tel_number, is_coord_valid
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (code, "senior_center", c_name, c_addr, c_lat, c_lon, tel, 1))

    connection.commit()


def main():
    """모든 데이터 생성 및 적재 파이프라인을 실행합니다."""
    print("1. 데이터베이스 테이블 생성 중...")
    create_tables()

    connection = get_db_connection()

    print("2. 기존 데이터 초기화 중...")
    clear_existing_data(connection)

    print("3. 데이터 출처 등록 중...")
    insert_sources(connection)

    print("4. 행정구역 및 인구 통계 데이터 삽입 중...")
    insert_regions_and_populations(connection)

    print("5. 의료 및 복지 시설(경로당, 병의원) 데이터 삽입 중...")
    insert_facilities(connection)

    connection.close()
    print("완료: caremap.db 데이터베이스가 성공적으로 구축되었습니다!")


if __name__ == "__main__":
    main()
