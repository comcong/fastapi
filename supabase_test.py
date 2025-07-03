from supabase import create_client, Client
import pandas as pd
# Supabase 연결 설정
url = 'https://hkfkdskgcaeviqhcarqi.supabase.co'
api_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhrZmtkc2tnY2FldmlxaGNhcnFpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTE1NDk1MjEsImV4cCI6MjA2NzEyNTUyMX0.qrQW5NVXMLBEMgFPXYPrC9Ka5V2xcr23qqBMBG9QQ1E'

supabase: Client = create_client(url, api_key)

def get_stock_data_from_db():
    try:
        # 전체 데이터 가져오기
        all_data = get_all_data("economic_and_stock_data")
        print(f"economic_and_stock_data 테이블에서 {len(all_data)}개 데이터를 성공적으로 가져왔습니다!")
        df = pd.DataFrame(all_data)

        # 날짜 열을 datetime으로 변환하고 정렬
        df['날짜'] = pd.to_datetime(df['날짜'])
        df.sort_values(by='날짜', inplace=True)

        # 결측치 처리
        print("결측치 처리 중...")
        df = df.ffill().bfill()  # 앞/뒤 값으로 결측치 채우기

        # 수치형 컬럼으로 변환
        exclude_columns = ['날짜']
        numeric_columns = [col for col in df.columns if col not in exclude_columns]
        df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric, errors='coerce')

        # NaN 비율 확인
        nan_ratios = df[numeric_columns].isna().mean()
        print("수치형 컬럼별 NaN 비율:")
        print(nan_ratios)

        # 유효한 데이터가 있는 컬럼만 dropna 대상으로 설정
        valid_columns = [col for col in numeric_columns if nan_ratios[col] < 1.0]
        df.dropna(subset=valid_columns, inplace=True)

        print(f"처리 후 데이터 크기: {df.shape}")
        return df
    except Exception as e:
        print(f"데이터 가져오기 오류: {e}")
        return None

def get_all_data(table_name):
    all_data = []
    offset = 0
    limit = 1000  # Supabase의 기본 제한
    while True:
        response = supabase.table(table_name).select("*").order("날짜", desc=False).limit(limit).offset(offset).execute()
        data = response.data
        if not data:  # 더 이상 데이터가 없으면 종료
            break
        all_data.extend(data)
        offset += limit
    return all_data