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
balance = []
d2_cash = ''
async def start_kis_receiver():
    global jango_df
    global balance
    col_names = ['매수_주문번호', '종목명', '종목코드', '체결시간', '주문수량', '체결수량', '체결단가', '현재가', '매도_주문가격', '매도_주문수량', '체결량', '체결잔량', '매도_주문번호']
    jango_df = jango_db(col_names)
    print('첫 시작 jango_df columns: ', jango_df.columns)
    balance = await update_balance('H0STCNI0')
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
                            json_data = jango_df.drop(columns='체결량').to_dict(orient="records")
                            data = {"type": "stock_data", "data": json_data}
                            print('json_data', data)
                            await websocket_manager.manager.broadcast(json.dumps(data))
                            print('데이터프레임 전송완료')
                            await update_balance(tr_id)

                        elif (tr_id in ['H0STCNI9', 'H0STCNI0']) and (data['체결여부'].values.tolist()[0] == '2'):  # 체결통보 데이터
                            trans_df = data.copy()
                            print('체결통보 df')
                            if trans_df['매도매수구분'].values[0] == '02':    # 01: 매도, 02: 매수
                                jango_df = await kis.buy_update(ws=ws, jango_df=jango_df, trans_df=trans_df)
                                jango_df = jango_df[col_names]  # buy_update 에서 새로운 주문일 때 컬럼이 늘어남

                            elif trans_df['매도매수구분'].values[0] == '01':    # 01: 매도, 02: 매수
                                print('체결통보')
                                print('체결수량:  ', trans_df.at[0, '체결수량'])
                                jango_df = await kis.sell_update(ws=ws, jango_df=jango_df, trans_df=trans_df) #, d2_cash=d2_cash)
                                # jango_df = res[0]
                                # if res[1] == '0':
                            asyncio.create_task(update_balance(tr_id))
                            jango_df = jango_df.sort_values(by='매수_주문번호').apply(lambda col: col.fillna(''))
                            cols = ['주문수량', '체결수량', '체결단가', '매도_주문가격']
                            jango_df[cols] = jango_df[cols].apply(lambda col: col.astype(str).str.lstrip('0'))

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
        await asyncio.sleep(5)  # 재연결 대기
        print('5초간 대기')


def jango_db(col_names):
    supa_db = kis_db.get_data()
    jango_df = pd.DataFrame(supa_db, columns=col_names).sort_values('체결시간')
    return jango_df

async def send_initial_data(websocket):
    jango_json_data = jango_df.fillna('').to_dict(orient="records")
    print('직렬화 전')
    print(jango_json_data)
    stock_data = {"type": "stock_data", "data": jango_json_data}
    stock_data = safe_for_json(stock_data)
    await websocket.send_text(json.dumps(stock_data))

def update_price(df: pd.DataFrame = None) -> pd.DataFrame:
    global jango_df  # 실시간 현재가 데이터 전역변수 사용
    jango_df = pd.merge(jango_df, df, on='종목코드', how='left')  # 병합
    jango_df.loc[jango_df["새현재가"].notna(), "현재가"] = jango_df["새현재가"]
    jango_df = jango_df.drop(columns=['새현재가'])


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
    jango_df.loc[mask, '수익률'] = 수익률.astype(str)

    print('update_jango_df 종료')

    return jango_df

def safe_for_json(d):
    for item in d['data']:
        for k, v in item.items():
            if isinstance(v, float) and math.isnan(v):
                item[k] = ""  # 또는 None, "NaN" 등
    return d


async def update_balance(trid):
    print('update_balance() 실행')
    global d2_cash
    fee_rate = 0.00015
    tax_rate = 0.0015
    if trid in ['H0STCNI9', 'H0STCNI0']:
        d2_cash = int(account_balance.get_balance())
    매입금액 = int((jango_df['체결수량'].astype('int') * jango_df['체결단가'].astype('int')).sum())
    매입수수료 = 매입금액 * fee_rate
    평가금액 = int((jango_df['체결수량'].astype('int') * jango_df['현재가'].astype('int')).sum())
    매도수수료 = 평가금액 * fee_rate
    세금 = 평가금액 * tax_rate
    평가금액 = 평가금액 - 매입수수료 - 매도수수료 - 세금
    balance = d2_cash + 매입금액
    tot_acc_value = d2_cash + 평가금액

    data = {'balance': balance, 'tot_acc_value': tot_acc_value, 'd2_cash': d2_cash}
    balance_data = {"type": "balance", "data": data}
    await websocket_manager.manager.broadcast(json.dumps(balance_data))

    return balance, tot_acc_value, d2_cash