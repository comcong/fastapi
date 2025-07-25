from supabase import create_client, Client
from app.core.config import settings
import pandas as pd
import random

url: str = settings.SUPABASE_URL
key: str = settings.SUPABASE_KEY
supabase: Client = create_client(url, key)

# 샘플 데이터
# data = {
#     "tr_id": "HOSTCNI9",
#     "고객ID": "C001",
#     "계좌번호": "12345678",
#     "주문번호": "ORD001",
#     "원주문번호": "ORD000",
#     "매도매수구분": "매수",
#     "정정구분": "신규",
#     "주문종류": "지정가",
#     "주문조건": "없음",
#     "종목코드": "005930",
#     "체결수량": 10,
#     "체결단가": 70000,
#     "체결시간": "104512",
#     "거부여부": "N",
#     "체결여부": "Y",
#     "접수여부": "Y",
#     "지점번호": "001",
#     "주문수량": 10,
#     "계좌명": "홍길동",
#     "호가조건가격": 70000,
#     "주문거래소구분": "코스피",
#     "실시간체결창표시여부": "Y",
#     "필러": "",
#     "신용구분": "현금",
#     "신용대출일자": "",
#     "체결종목명": "삼성전자",
#     "주문가격": 70000
# }

def get_data():
    """Supabase에서 데이터 가져오기"""
    try:
        data = supabase.table('transaction_info').select("*").limit(None).execute().data
        print(f"데이터를 성공적으로 가져왔습니다!")
        return data
    except Exception as e:
        print(f"데이터 가져오기 오류: {e}")
        return None

def insert_data(data):
    try:
        response = supabase.table("transaction_info").insert(data).execute()
        print("데이터 삽입 성공")

    except Exception as e:
        print("데이터 삽입 실패:", e)

def delete_data(oder_no):
    # 특정 주문번호로 행 삭제
    order_id_to_delete = oder_no
    response = supabase.table("transaction_info").delete().eq('주문번호', oder_no).execute()

    print("삭제 결과:", response)

# 테스트용
def generate_order_id():
    number = random.randint(1, 999)  # 1부터 999까지
    return f"ORD{number:03d}"  # 3자리로 포맷팅 (예: 1 → 001)


# if __name__ == '__main__':
#     # insert_data(data)
#     delete_data('ORD347')
#     get_data()

