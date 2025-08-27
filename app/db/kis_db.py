# kis_db.py
from supabase import create_client, Client
from app.core.config import settings
import random
from datetime import datetime
import traceback

url: str = settings.SUPABASE_URL
key: str = settings.SUPABASE_KEY
supabase: Client = create_client(url, key)

# 샘플 데이터
# ['삼성전자', '한국전력', '한전기술', '현대차', '기아', '아주IB투자']
#  ['005930', '015760', '052690', '005380', '000270', '027360']
data = [
        {"종목명": "현대차",
         "종목코드": "005380",
         "매수_주문번호": "25080821148",
         "체결수량": '100',
         "체결단가": '90000',
         "현재가": '91000',
         "체결시간": "250809150954",
         "주문수량": '10',
         "매도_주문가격": '70000',
         "매도_주문번호": "25080825416",}
        ]

def get_data():
    """Supabase에서 데이터 가져오기"""
    try:
        data = supabase.table('transaction_info').select("*").limit(None).execute().data
        print(f"데이터를 성공적으로 가져왔습니다!")
        print(data)
        return data
    except Exception as e:
        print(f"데이터 가져오기 오류: {e}")
        return None

def del_and_insert(safe_df):
    try:
        # 1. 기존 데이터 삭제
        supabase.table("transaction_info").delete().neq("매수_주문번호", None).execute()
        print("기존 데이터 삭제 완료")

        # 2. records 생성
        json_data = safe_df.to_dict(orient="records")

        # 1. 새로운 데이터 삽입
        if json_data:  # 비어있으면 False, 하나라도 있으면 True
            res = supabase.table("transaction_info").insert(json_data).execute()
            print("삽입한 새로운 데이터", res)
        else:
            print("데이터가 없어서 insert 생략")
    except Exception as e:
        print("트랜잭션 처리 중 오류 발생:", e)
        print(traceback.format_exc())



def insert_data(jango_data):
    try:
        res = supabase.table("acc_jango").insert(jango_data).execute()
        print("jango_data 데이터 삽입 성공", res)
    except Exception as e:
        print("jango_data 데이터 삽입 실패:", e)

def delete_data():
    try:
        supabase.table("transaction_info").delete().neq("매수_주문번호", None).execute()
        print("데이터 삭제 성공")
    except Exception as e:
        print("데이터 삭제 실패:", e)

def update_data(data: list):
    print(data)
    try:
        for i in data:
            i["actor"] = "server:fastapi"
            supabase.table("transaction_info").update(i).eq("매수_주문번호", i['주문번호']).execute()
        print("데이터 업데이트 성공:")
    except Exception as e:
        print("데이터 업데이트 실패:", e)

def upsert_data(data: list):
    print('upsert_data 실행')
    supabase.table("transaction_info").upsert(
        data,
        on_conflict="매수_주문번호",
        ignore_duplicates=False,
        default_to_null=False
    ).execute()
    print("데이터 업데이트 성공:")


# 테스트용
def generate_order_id():
    number = random.randint(1, 999)  # 1부터 999까지
    return f"ORD{number:03d}"  # 3자리로 포맷팅 (예: 1 → 001)


if __name__ == '__main__':
    # pass
    insert_data(data)
    # delete_data()
    # get_data()

