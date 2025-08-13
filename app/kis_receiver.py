# kis_receiver.py
import asyncio
import json
import pandas as pd
import websockets
import traceback
import math

import websocket_manager
from app.core.config import settings
from app.db import kis_db
from app.kis_invesment.kis_manager import kis
from app.kis_invesment import account_balance

jango_df: pd.DataFrame = pd.DataFrame()
col_names = ['매수_주문번호', '종목명', '종목코드', '체결시간', '주문수량', '체결수량', '체결단가', '현재가', '수익률', '매도_주문가격', '매도_주문번호']
d2_cash = account_balance.get_balance()
balance = ''

# 잔고 = 예수금 + (DataFrame 내 남아있는 모든 매수 잔고의 매입금액 총합)

async def start_kis_receiver():
    global jango_df
    global balance
    jango_df = jango_db()
    # 체결시간_포맷()
    code_list = jango_df['종목코드'].unique().tolist()  # DB 에서 종목코드 가져옴



    매입금액_총합 = (jango_df['체결수량'].astype(int) * jango_df['체결단가'].astype(int)).sum()
    # 전역 상태로 관리되는 잔고 변수
    balance = str(d2_cash + 매입금액_총합)  # 초기 잔고
    # 매도 체결이 들어올 때 함수 호출


    async with websockets.connect(settings.ws_url) as ws:
        await kis.subscribe(ws=ws)
        await kis.subscribe(ws=ws, tr_id='H0STCNT0', code_list=code_list)

        while True:
            try:
                raw_data = await ws.recv()        # ws로부터 데이터 수신
                # print("수신된 원본 데이터: ")
                # print(raw_data)
                data = await kis.make_data(raw_data)  # 데이터 가공
                print("수신된 가공 데이터: ")
                print(data)

                if isinstance(data, pd.DataFrame):
                    tr_id = data.iloc[0]['tr_id']
                    if tr_id == 'H0STCNT0':            # 실시간 현재가가 들어오는 경우
                        print('tr_id == "H0STCNT0":')

                        jango_df = update_jango_df(data[['종목코드', '새현재가']].copy())
                        jango_df = jango_df[col_names]
                        cols = ['주문수량', '체결수량', '체결단가', '매도_주문가격']
                        jango_df[cols] = jango_df[cols].apply(lambda col: col.astype(str).str.lstrip('0'))
                        json_data = jango_df.to_dict(orient="records")
                        data = {"type": "stock_data", "data": json_data}
                        print('json_data', data)
                        await websocket_manager.manager.broadcast(json.dumps(data))
                        print('데이터프레임 전송완료')

                    elif (tr_id in ['H0STCNI9', 'H0STCNI0']) and (data['체결여부'].values.tolist()[0] == '2'):  # 체결통보 데이터
                        # sanare78^5014279001^0000001562^^02^0^00^0^027360^0000000001^000002200^092701^0^1^1^00950^000000001^신명진^1Y^10^^아주IB투자^
                        trans_df = data.copy()
                        print('체결통보 df')
                        if trans_df['매도매수구분'].values[0] == '02':    # 01: 매도, 02: 매수
                            jango_df = await kis.buy_update(ws=ws, jango_df=jango_df, trans_df=trans_df)

                        elif trans_df['매도매수구분'].values[0] == '01':    # 01: 매도, 02: 매수
                            balance = update_balance(jango_df, balance, trans_df['주문번호'][0], trans_df['체결수량'][0], trans_df['체결단가'][0])
                            # def update_balance(df, current_balance, sell_order_no, sell_qty, sell_price):

                            jango_df = kis.sell_update(jango_df=jango_df, trans_df=trans_df)
                        print(jango_df)
                        print(jango_df.columns)
                        jango_df = jango_df[col_names].sort_values(by='매수_주문번호').fillna('')
                        cols = ['주문수량', '체결수량', '체결단가', '매도_주문가격']
                        jango_df[cols] = jango_df[cols].apply(lambda col: col.astype(str).str.lstrip('0'))
                        json_data = jango_df.to_dict(orient="records")
                        data = {"type": "stock_data", "data": json_data}
                        print('json_data', data)
                        await websocket_manager.manager.broadcast(json.dumps(data))
                        print('데이터프레임 전송완료')

                else:
                    msg_data = {"type": "message", "data": data}
                    await websocket_manager.manager.broadcast(json.dumps(msg_data))
                    print('json 전송완료')



            except Exception as e:
                print("웹소켓 수신 오류: 1", e)
                traceback.print_exc()





def jango_db():
    supa_db = kis_db.get_data()
    jango_df = pd.DataFrame(supa_db, columns=col_names).sort_values('체결시간')
    return jango_df

async def send_initial_data(websocket):
    jango_json_data = strip_zeros(jango_df.to_dict(orient="records"))
    print('직렬화 전')
    print(jango_json_data)
    stock_data = {"type": "stock_data", "data": jango_json_data}
    stock_data = safe_for_json(stock_data)
    await websocket.send_text(json.dumps(stock_data))

# 숫자 앞 0을 없애주는 함수
def strip_zeros(json_list: list[dict]) -> list[dict]:
    keys_to_strip_zeros = ['주문수량', '체결수량', '체결단가', '매도_주문가격']
    for record in json_list:
        for key in keys_to_strip_zeros:
            if key in record and record[key]:
                try:
                    record[key] = str(int(record[key]))
                except (ValueError, TypeError):
                    pass  # 숫자 변환 불가능한 값은 건너뜀
    return json_list

def update_jango_df(df: pd.DataFrame = None) -> pd.DataFrame:
    global jango_df  # 실시간 현재가 데이터 전역변수 사용
    if df is None:
        return jango_df
    else:
        jango_df = pd.merge(jango_df, df, on='종목코드', how='left')  # 병합
        jango_df.loc[jango_df["새현재가"].notna(), "현재가"] = jango_df["새현재가"]
        jango_df = jango_df.drop(columns=['새현재가'])

        fee_rate = 0.00015
        tax_rate = 0.002
        매수가 = jango_df['체결단가'].astype(int)
        매수_수수료 = 매수가 * fee_rate
        실제_매수금액 = 매수가 + 매수_수수료

        매도가 = jango_df['현재가'].astype(int)
        매도_수수료 = 매도가 * fee_rate
        세금 = 매도가 * tax_rate
        실제_매도금액 = 매도가 - 매도_수수료 - 세금

        jango_df['수익률'] = round(((실제_매도금액 - 실제_매수금액) / 실제_매수금액) * 100, 2).astype(str)


        return jango_df

def safe_for_json(d):
    for item in d['data']:
        for k, v in item.items():
            if isinstance(v, float) and math.isnan(v):
                item[k] = ""  # 또는 None, "NaN" 등
    return d


def update_balance(df, current_balance, sell_order_no, sell_qty, sell_price):
    """
    df: 현재 보유잔고 DataFrame (매수 주문들)
    current_balance: 현재 잔고 (int or float)
    sell_order_no: 실제 매도된 매도 주문번호 (str)
    sell_qty: 매도 체결 수량 (int)
    sell_price: 매도 체결 가격 (int or float)

    반환: 업데이트된 잔고 (int or float)
    """
    # 1. 매도주문번호가 매수_주문번호 컬럼과 일치하는 행 찾기
    matched_rows = df[df['매도_주문번호'] == sell_order_no]

    if matched_rows.empty:
        # 매도주문번호와 매칭되는 매수 주문이 없으면 예외처리 또는 기존 잔고 반환
        print("Error: 매도 주문번호에 해당하는 매수 주문을 찾을 수 없습니다.")
        return current_balance

    # 2. 매입단가(체결단가) 가져오기 (여기선 첫 행 기준, 매수_주문번호는 유니크하므로 한 행만 있음)
    buy_price = int(matched_rows.iloc[0, '체결단가'])

    # 3. 매도 체결 수량만큼 매입금액 차감
    purchase_cost_reduction = int(sell_qty) * buy_price

    # 4. 매도 체결 금액 계산
    sell_revenue = sell_qty * sell_price

    # 5. 잔고 업데이트
    updated_balance = current_balance - purchase_cost_reduction + sell_revenue

    return updated_balance
