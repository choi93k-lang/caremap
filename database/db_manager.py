import os
import sqlite3
import pandas as pd

# 데이터베이스 파일 경로 상수
DB_PATH = os.path.join(os.path.dirname(__file__), "caremap.db")


def get_db_connection():
    """데이터베이스 연결 객체를 생성하여 반환합니다."""
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row  # 딕셔너리처럼 컬럼명으로 접근 가능하게 설정
    return connection


def create_tables():
    """데이터베이스 테이블이 없으면 생성합니다."""
    connection = get_db_connection()
    cursor = connection.cursor()

    # 1. 행정구역 마스터 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS region (
            region_code TEXT PRIMARY KEY,
            district_name TEXT NOT NULL,
            dong_name TEXT NOT NULL
        )
    """)

    # 2. 고령인구 통계 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS population (
            pop_id INTEGER PRIMARY KEY AUTOINCREMENT,
            region_code TEXT NOT NULL,
            base_year_month TEXT NOT NULL,
            total_population INTEGER NOT NULL,
            elderly_population INTEGER NOT NULL,
            elderly_male INTEGER NOT NULL,
            elderly_female INTEGER NOT NULL,
            aging_rate REAL NOT NULL,
            FOREIGN KEY (region_code) REFERENCES region (region_code)
        )
    """)

    # 3. 시설 정보 테이블 (경로당, 병원)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS facility (
            facility_id INTEGER PRIMARY KEY AUTOINCREMENT,
            region_code TEXT NOT NULL,
            facility_type TEXT NOT NULL,
            facility_name TEXT NOT NULL,
            road_address TEXT,
            latitude REAL,
            longitude REAL,
            tel_number TEXT,
            is_coord_valid INTEGER DEFAULT 1,
            FOREIGN KEY (region_code) REFERENCES region (region_code)
        )
    """)

    # 4. 데이터 출처 관리 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS source (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_name TEXT NOT NULL,
            provider TEXT NOT NULL,
            url TEXT,
            base_date TEXT
        )
    """)

    connection.commit()
    connection.close()


def get_all_districts():
    """울산광역시 구·군 목록을 중복 없이 가져옵니다."""
    connection = get_db_connection()
    query = "SELECT DISTINCT district_name FROM region ORDER BY district_name"
    df = pd.read_sql_query(query, connection)
    connection.close()
    return ["전체"] + df["district_name"].tolist()


def get_population_summary(district_name="전체"):
    """구·군별 또는 전체 인구 및 고령화율 데이터를 조회합니다."""
    connection = get_db_connection()
    if district_name == "전체":
        query = """
            SELECT 
                r.district_name,
                r.dong_name,
                r.region_code,
                p.total_population,
                p.elderly_population,
                p.elderly_male,
                p.elderly_female,
                p.aging_rate
            FROM region r
            JOIN population p ON r.region_code = p.region_code
            ORDER BY p.aging_rate DESC
        """
        df = pd.read_sql_query(query, connection)
    else:
        query = """
            SELECT 
                r.district_name,
                r.dong_name,
                r.region_code,
                p.total_population,
                p.elderly_population,
                p.elderly_male,
                p.elderly_female,
                p.aging_rate
            FROM region r
            JOIN population p ON r.region_code = p.region_code
            WHERE r.district_name = ?
            ORDER BY p.aging_rate DESC
        """
        df = pd.read_sql_query(query, connection, params=(district_name,))
    connection.close()
    return df


def get_facilities(district_name="전체", facility_type="all"):
    """조건에 맞는 시설 목록을 데이터프레임으로 조회합니다."""
    connection = get_db_connection()
    conditions = []
    params = []

    if district_name != "전체":
        conditions.append("r.district_name = ?")
        params.append(district_name)

    if facility_type != "all":
        conditions.append("f.facility_type = ?")
        params.append(facility_type)

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT 
            f.facility_id,
            f.facility_name,
            f.facility_type,
            f.road_address,
            f.latitude,
            f.longitude,
            f.tel_number,
            f.is_coord_valid,
            r.district_name,
            r.dong_name
        FROM facility f
        JOIN region r ON f.region_code = r.region_code
        {where_clause}
    """
    df = pd.read_sql_query(query, connection, params=params)
    connection.close()
    return df


def get_region_comparison_data():
    """모든 행정동의 인구와 시설 수를 결합하여 비교 지표를 조회합니다."""
    connection = get_db_connection()
    query = """
        SELECT 
            r.region_code,
            r.district_name,
            r.dong_name,
            p.total_population,
            p.elderly_population,
            p.aging_rate,
            COUNT(CASE WHEN f.facility_type = 'hospital' THEN 1 END) AS hospital_count,
            COUNT(CASE WHEN f.facility_type = 'senior_center' THEN 1 END) AS senior_center_count,
            COUNT(f.facility_id) AS total_facility_count
        FROM region r
        JOIN population p ON r.region_code = p.region_code
        LEFT JOIN facility f ON r.region_code = f.region_code
        GROUP BY r.region_code, r.district_name, r.dong_name, p.total_population, p.elderly_population, p.aging_rate
    """
    df = pd.read_sql_query(query, connection)
    connection.close()

    # 고령인구 1,000명당 시설 수 계산 (0으로 나누기 방지)
    df["hospitals_per_1k"] = df.apply(
        lambda row: round((row["hospital_count"] / row["elderly_population"]) * 1000, 2)
        if row["elderly_population"] > 0 else 0,
        axis=1
    )
    df["centers_per_1k"] = df.apply(
        lambda row: round((row["senior_center_count"] / row["elderly_population"]) * 1000, 2)
        if row["elderly_population"] > 0 else 0,
        axis=1
    )
    return df

