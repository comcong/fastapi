# kis_receiver.py
import asyncio
import json
import pandas as pd
import websockets
import math

import websocket_manager
from app.core.config import settings
from app.db import kis_db
from app.kis_invesment.kis_manager import kis
from app.kis_invesment import account_balance

jango_df = None
d2_cash = int(account_balance.get_balance())
async def start_kis_receiver():
    global jango_df
    col_names = ['매수_주문번호', '종목명', '종목코드', '체결시간', '주문수량', '체결수량', '체결단가', '현재가', '매도_주문가격', '매도_주문수량', '체결량', '체결잔량', '매도_주문번호']
    jango_df = jango_db(col_names) #.sort_values(by='매수_주문번호')
    print('jango_df_1', '\n', jango_df.shape)
    code_list = jango_df['종목코드'].unique().tolist()  # DB 에서 종목코드 가져옴

    while True:
        try:
            async with websockets.connect(settings.ws_url) as ws:
                await kis.subscribe(ws=ws)
                await kis.subscribe(ws=ws, tr_id='H0STCNT0', code_list=code_list)

                while True:
                    raw_data = await ws.recv()
                    data = await kis.make_data(raw_data)  # 데이터 가공
                    print("수신된 가공 데이터: ")
                    print(data)

                    if isinstance(data, pd.DataFrame):
                        tr_id = data.iloc[0]['tr_id']
                        if tr_id == 'H0STCNT0':            # 실시간 현재가가 들어오는 경우
                            print('tr_id == "H0STCNT0":')
                            jango_df = update_price(data[['종목코드', '새현재가']].copy())
                            print('jango_df_2', '\n', jango_df.shape)
                            # json_data = jango_df.drop(columns='체결량').to_dict(orient="records")
                            await send_update_balance()

                        elif (tr_id in ['H0STCNI9', 'H0STCNI0']) and (data['체결여부'].values.tolist()[0] == '2'):  # 체결통보 데이터
                            trans_df = data.copy()
                            if trans_df['매도매수구분'].values[0] == '02':    # 01: 매도, 02: 매수
                                print('매수 체결통보')
                                jango_df = await kis.buy_update(ws=ws, jango_df=jango_df, trans_df=trans_df)
                                print('jango_df_3', '\n', jango_df.shape)
                                jango_df = jango_df[col_names]

                            elif trans_df['매도매수구분'].values[0] == '01':    # 01: 매도, 02: 매수
                                print('매도 체결통보')
                                print('체결수량:  ', trans_df.at[0, '체결수량'])
                                jango_df = await kis.sell_update(ws=ws, jango_df=jango_df, trans_df=trans_df)
                                print('jango_df_4', '\n', jango_df.shape)

                            jango_df = jango_df.where(pd.notna(jango_df), None)  # nan 을 None 로 변환
                            asyncio.create_task(send_update_balance(tr_id))

                        jango_df = jango_df.sort_values(by='매수_주문번호')
                        print('jango_df_5', '\n', jango_df.shape)
                        cols = ['주문수량', '체결수량', '체결단가']
                        jango_df[cols] = jango_df[cols].apply(lambda col: col.astype(str).str.lstrip('0'))
                        print('jango_df_10', '\n', jango_df.shape)

                        json_data = jango_df.drop(columns='체결량').to_dict(orient="records")
                        data = {"type": "stock_data", "data": json_data}
                        print('json_data', data)
                        await websocket_manager.manager.broadcast(json.dumps(data))
                        print('데이터프레임 전송완료')

                    else:
                        msg_data = {"type": "message", "data": data}
                        await websocket_manager.manager.broadcast(json.dumps(msg_data))
                        print('json 전송완료')

        except websockets.ConnectionClosedError as e:
            print("웹소켓 수신 오류:", e)
        except ConnectionAbortedError as e:
            print("네트워크 연결 끊김:", e)
        except Exception as e:
            print("start_kis_receiver 예외:", e)
            print("예외 시점 jango_df.shape:", jango_df.shape)
        await asyncio.sleep(5)  # 재연결 대기
        print('5초간 대기')


def jango_db(col_names):
    supa_db = kis_db.get_data()
    jango_df = pd.DataFrame(supa_db, columns=col_names).sort_values('체결시간')
    return jango_df

async def send_initial_data(websocket):
    # jango_json_data = jango_df.fillna('').to_dict(orient="records")
    jango_json_data = jango_df.to_dict(orient="records")
    print('직렬화 전')
    print(jango_json_data)
    stock_data = {"type": "stock_data", "data": jango_json_data}
    # stock_data = safe_for_json(stock_data)
    await websocket.send_text(json.dumps(stock_data))

def safe_for_json(d):
    for item in d['data']:
        for k, v in item.items():
            if isinstance(v, float) and math.isnan(v):
                item[k] = ""  # 또는 None, "NaN" 등
    return d


def update_price(df: pd.DataFrame = None) -> pd.DataFrame:
    print('update_price() 실행')
    global jango_df  # 실시간 현재가 데이터 전역변수 사용
    jango_df = pd.merge(jango_df, df, on='종목코드', how='left')
    print('jango_df_7', '\n', jango_df.shape)
    mask = jango_df["새현재가"].notna()
    jango_df.loc[mask, "현재가"] = jango_df.loc[mask, "새현재가"]
    jango_df = jango_df.drop(columns=['새현재가'])
    print('jango_df_8', '\n', jango_df.shape)


    # 수익률 계산
    fee_rate = 0.00015
    tax_rate = 0.0015
    mask = pd.to_numeric(jango_df["현재가"], errors="coerce").notna()
    매수가 = jango_df.loc[mask, '체결단가'].astype(int)
    매도가 = jango_df.loc[mask, '현재가'].astype(int)
    매수_수수료 = 매수가 * fee_rate
    매도_수수료 = 매도가 * fee_rate
    세금 = 매도가 * tax_rate
    수익률 = round((매도가 - 매수가 - 매수_수수료 - 매도_수수료 - 세금) / 매수가 * 100, 2)
    print('수익률: ', '\n', 수익률, '\n')

    print('update_price() 종료')

    return jango_df

async def send_update_balance(tr_id=''):
    data = await update_balance(tr_id)
    if data:
        data = {'balance': data[0], 'tot_acc_value': data[1], 'acc_profit': data[2], 'd2_cash': data[3]}
        balance_data = {"type": "balance", "data": data}
        await websocket_manager.manager.broadcast(json.dumps(balance_data))

async def update_balance(tr_id=''):
    print('update_balance() 실행')
    global d2_cash
    fee_rate = 0.00015
    tax_rate = 0.0015
    if tr_id in ['H0STCNI9', 'H0STCNI0']:
        d2_cash = int(account_balance.get_balance())

    mask = (jango_df['현재가'] == "") | (jango_df['현재가'].isna())  # 현재가가 없는 행 찾기
    if mask.any():  # 현재가가 없는 행이 하나라도 있으면 패스
        return None  # None 을 반환하고 종료
    else:           # 현재가가 모든 행에 전부 있으면
        try:
            매입금액 = int((jango_df['체결수량'].astype('int') * jango_df['체결단가'].astype('int')).sum())
            매입수수료 = int(매입금액 * fee_rate)
            평가금액 = int((jango_df['체결수량'].astype('int') * jango_df['현재가'].astype('int')).sum())
            매도수수료 = int(평가금액 * fee_rate)
            세금 = int(평가금액 * tax_rate)
            평가금액 = 평가금액 - 매입수수료 - 매도수수료 - 세금
            balance = d2_cash + 매입금액
            tot_acc_value = d2_cash + 평가금액
            acc_profit = tot_acc_value - balance

            # data = {'balance': balance, 'tot_acc_value': tot_acc_value,  'acc_profit': acc_profit, 'd2_cash': d2_cash}
            # balance_data = {"type": "balance", "data": data}
            # await websocket_manager.manager.broadcast(json.dumps(balance_data))
            # print('update_balance() 종료')
            return balance, tot_acc_value, acc_profit, d2_cash
        except Exception as e:
            print('update_balance() 에러:  ', e)

# async def broadcast_stock_data(df, websocket_manager):
#     """
#     DataFrame을 WebSocket으로 전송.
#     - '체결량' 컬럼 제거
#     - NaN 값을 None으로 변환 (JS에서 null로 표시됨)
#     - dict 형태로 변환 후 broadcast
#     """
#     def safe_value(v):
#         if isinstance(v, float) and math.isnan(v):
#             return None
#         return v
#
#     def safe_dict(d):
#         return {k: safe_value(v) for k, v in d.items()}
#
#     # '체결량' 컬럼 제거 후 dict 변환
#     json_data = df.drop(columns='체결량').where(pd.notna(df), None).to_dict(orient="records")
#     json_data = [safe_dict(row) for row in json_data]  # NaN → None 재확인
#
#     data = {"type": "stock_data", "data": json_data}
#
#     print("json_data", data)
#
#     # WebSocket broadcast
#     await websocket_manager.manager.broadcast(json.dumps(data))