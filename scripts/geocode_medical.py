"""
scripts/geocode_medical.py

울산광역시 1,401개 실제 의료기관의 도로명주소를 위도·경도(WGS84)로 변환(지오코딩)하는 스크립트입니다.
결과는 data/raw/medical_coords_cache.json 에 안전하게 저장되며,
이미 변환된 주소는 캐시에서 바로 불러옵니다.
"""

import os
import sys
import re
import json
import time
import urllib.request
import urllib.parse
import pandas as pd

# UTF-8 출력 보장
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_CSV = os.path.join(BASE_DIR, "data", "raw", "ulsan_medical_raw.csv")
CACHE_FILE = os.path.join(BASE_DIR, "data", "raw", "medical_coords_cache.json")


def clean_road_address(address_string):
    """
    상세 층수나 호수(예: 2층 201호), 건물명 등 부가정보를 제거하고
    '울산광역시 구/군 도로명 건물번호' 형태만 추출합니다.
    """
    if not isinstance(address_string, str):
        return ""
    
    # 1. 괄호 앞부분 추출
    clean_addr = address_string.split("(")[0].strip()
    
    # 2. 울산광역시 + 구/군 + 도로명 + 번지 패턴 정규식
    pattern = r"(울산광역시\s+[가-힣]+[구|군]\s+[가-힣0-9·\-]+(?:로|길|대로|거리)\s+\d+(?:-\d+)?)"
    match = re.search(pattern, clean_addr)
    if match:
        return match.group(1).strip()
    
    # 층, 호 등 제거
    clean_addr = re.sub(r"\s+\d+층.*", "", clean_addr)
    clean_addr = re.sub(r"\s+\d+호.*", "", clean_addr)
    return clean_addr.strip()


def query_nominatim(query_text):
    """오픈스트리트맵 Nominatim API를 통해 주소 또는 명칭의 위도·경도를 조회합니다."""
    url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(query_text)}&format=json"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "UlsanCareMapGeocoding/1.0 (contact: choi@caremap.local)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            result = json.loads(response.read().decode("utf-8"))
            if result and len(result) > 0:
                lat = float(result[0]["lat"])
                lon = float(result[0]["lon"])
                # 울산 광역 경계(위도 35.3~35.7, 경도 129.0~129.5) 범위 내인지 검증
                if 35.3 <= lat <= 35.8 and 129.0 <= lon <= 129.6:
                    return lat, lon
    except Exception as error:
        pass
    return None, None


def main():
    if not os.path.exists(RAW_CSV):
        print(f"[오류] 의료기관 원본 파일이 없습니다: {RAW_CSV}")
        return

    # 기존 캐시 불러오기
    coords_cache = {}
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                coords_cache = json.load(f)
            print(f"[알림] 기존 캐시 {len(coords_cache)}개 항목 로드 완료")
        except Exception:
            coords_cache = {}

    # CSV 로드
    df = pd.read_csv(RAW_CSV, encoding="euc-kr")
    total_rows = len(df)
    print(f"[알림] 총 {total_rows}개 의료기관 지오코딩을 시작합니다.")

    # 주소 정리 컬럼 추가
    df["clean_addr"] = df["소재지"].apply(clean_road_address)
    unique_addrs = [addr for addr in df["clean_addr"].unique() if addr]

    print(f"[알림] 고유 도로명주소 개수: {len(unique_addrs)}개")

    new_geocoded_count = 0
    save_counter = 0

    for idx, addr in enumerate(unique_addrs, 1):
        if addr in coords_cache:
            continue

        lat, lon = query_nominatim(addr)
        
        # 도로명+건물번호로 못 찾은 경우, 도로명까지만 검색하여 해당 도로 위에 배치
        if lat is None:
            road_only = re.sub(r"\s+\d+(?:-\d+)?$", "", addr)
            if road_only != addr:
                lat, lon = query_nominatim(road_only)

        # 찾은 경우 캐시에 저장
        if lat is not None and lon is not None:
            coords_cache[addr] = [round(lat, 7), round(lon, 7)]
            new_geocoded_count += 1
            print(f"[{idx}/{len(unique_addrs)}] 성공: {addr} -> ({lat:.6f}, {lon:.6f})")
        else:
            print(f"[{idx}/{len(unique_addrs)}] 미확인: {addr}")

        save_counter += 1
        # 10건마다 중간 저장하여 작업 중단 시에도 보존
        if save_counter >= 10:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(coords_cache, f, ensure_ascii=False, indent=2)
            save_counter = 0

        # Nominatim 호출 제한 준수 (0.9초 대기)
        time.sleep(0.9)

    # 최종 캐시 저장
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(coords_cache, f, ensure_ascii=False, indent=2)

    print(f"\n[완료] 새로 변환된 주소: {new_geocoded_count}개, 전체 캐시 총계: {len(coords_cache)}개")


if __name__ == "__main__":
    main()
