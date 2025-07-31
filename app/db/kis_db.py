from supabase import create_client, Client
from app.core.config import settings
import pandas as pd
import random

url: str = settings.SUPABASE_URL
key: str = settings.SUPABASE_KEY
supabase: Client = create_client(url, key)

# 샘플 데이터
# ['삼성전자', '한국전력', '한전기술', '현대차', '기아', '아주IB투자']
#  ['005930', '015760', '052690', '005380', '000270', '027360']
data = [
        {"종목명": "현대차",
         "종목코드": "005380",
         "주문번호": "ORD0011",
         "고객ID": "C001",
         "계좌번호": "50142790",
         "원주문번호": "ORD000",
         "매도매수구분": "매수",
         "정정구분": "신규",
         "주문종류": "지정가",
         "주문조건": "없음",
         "체결수량": 10,
         "체결단가": 70000,
         "현재가": 0,
         "체결시간": "104512",
         "거부여부": "N",
         "체결여부": "Y",
         "접수여부": "Y",
         "지점번호": "001",
         "주문수량": 10,
         "계좌명": "홍길동",
         "호가조건가격": 70000,
         "주문거래소구분": "코스피",
         "실시간체결창표시여부": "Y",
         "필러": "",
         "신용구분": "현금",
         "신용대출일자": "",
         "주문가격": 70000}
        ]

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
        for i in data:
            supabase.table("transaction_info").insert(i).execute()
        print("데이터 삽입 성공")

    except Exception as e:
        print("데이터 삽입 실패:", e)

def delete_data():
    try:
        supabase.table("transaction_info").delete().neq("주문번호", None).execute()
        print("데이터 삭제 성공")
    except Exception as e:
        print("데이터 삭제 실패:", e)

def update_data(data: list):
    print(data)
    try:
        for i in data:
            supabase.table("transaction_info").update(i).eq("주문번호", i['주문번호']).execute()
        print("데이터 업데이트 성공:")
    except Exception as e:
        print("데이터 업데이트 실패:", e)


# 테스트용
def generate_order_id():
    number = random.randint(1, 999)  # 1부터 999까지
    return f"ORD{number:03d}"  # 3자리로 포맷팅 (예: 1 → 001)


if __name__ == '__main__':
    # pass
    insert_data(data)
    # delete_data('ORD001')
    # get_data()

