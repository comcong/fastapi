# kis_receiver.py
import asyncio
import json
import pandas as pd
import websockets
import math
from datetime import datetime

import websocket_manager
from app.core.config import settings
from app.db import kis_db
from app.kis_invesment.kis_manager import kis
from app.kis_invesment import account_balance

jango_df = None
d2_cash = int(account_balance.get_balance())
ordered = False
async def start_kis_receiver():
    global jango_df
    global ordered
    jango_df = jango_db(settings.col_names)
    print('jango_df_1', '\n', jango_df.shape)
    code_list = jango_df['종목코드'].unique().tolist()  # DB 에서 종목코드 가져옴

    while True:
        try:
            async with websockets.connect(settings.ws_url) as ws:
                await kis.subscribe(ws=ws)
                await kis.subscribe(ws=ws, tr_id='H0STCNT0', code_list=code_list)

                while True:
                    if jango_df.shape[0] == 0:
                        buy_json_data = {'code': '233740', 'quantity': str(50)}
                        await kis.buy_order(buy_json_data)
                        ordered = True
                    raw_data = await ws.recv()
                    data = await kis.make_data(raw_data)  # 데이터 가공

                    if isinstance(data, pd.DataFrame):
                        print("수신된 가공 데이터: ")
                        print(data.columns)
                        tr_id = data.iloc[0]['tr_id']
                        if tr_id == 'H0STCNT0':            # 실시간 현재가가 들어오는 경우
                            print('tr_id == "H0STCNT0":')
                            jango_df = await update_price(data[['종목코드', '새현재가']].copy())
                            print('jango_df_2', '\n', jango_df.shape)
                            await send_update_balance()

                        elif (tr_id in ['H0STCNI9', 'H0STCNI0']) and (data['체결여부'].values.tolist()[0] == '2'):  # 체결통보 데이터
                            trans_df = data.copy()
                            ordered = False
                            if trans_df['매도매수구분'].values[0] == '02':  # 매수       # 01: 매도, 02: 매수
                                print('매수 체결통보')
                                jango_df = await kis.buy_update(ws=ws, jango_df=jango_df, trans_df=trans_df)
                                print('jango_df_3', '\n', jango_df.shape)

                            elif trans_df['매도매수구분'].values[0] == '01': # 매도      # 01: 매도, 02: 매수
                                print('매도 체결통보')
                                print('체결수량:  ', trans_df.at[0, '체결수량'])
                                jango_df = await kis.sell_update(ws=ws, jango_df=jango_df, trans_df=trans_df)
                                print('jango_df_4', '\n', jango_df.shape)
                            data['새현재가'] = data['체결단가']
                            jango_df = await update_price(data[['종목코드', '새현재가']].copy())
                            # asyncio.create_task(send_update_balance(tr_id))  # 백그라운드로 send_update_balance() 실행
                            await send_update_balance(tr_id)

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
                        print("수신된 가공 데이터: ")
                        print(data)
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
    jango_df = pd.DataFrame(supa_db, columns=col_names).sort_values('매수_주문번호')
    return jango_df

async def send_initial_data(websocket):
    jango_json_data = jango_df.to_dict(orient="records")
    print('직렬화 전')
    print(jango_json_data)
    stock_data = {"type": "stock_data", "data": jango_json_data}
    await websocket.send_text(json.dumps(stock_data))

async def update_price(df: pd.DataFrame = None) -> pd.DataFrame:
    print('update_price() 실행')
    global jango_df
    global ordered
    jango_df = pd.merge(jango_df, df, on='종목코드', how='left')
    print('jango_df_7', '\n', jango_df.shape)
    mask = jango_df["새현재가"].notna()
    jango_df.loc[mask, "현재가"] = jango_df.loc[mask, "새현재가"]
    jango_df = jango_df.drop(columns=['새현재가'])
    print('jango_df_8', '\n', jango_df.shape)
    sell_to_buy_order_map = kis.get_sell_to_buy_order_map()
    buy_현재가 = jango_df['현재가'].astype('int')
    buy_체결단가 = jango_df['체결단가'].astype('int')
    buy_profit = (buy_현재가 - buy_체결단가) / buy_체결단가
    print('buy_profit', '\n', buy_profit * 100)
    buy_profit = buy_profit.iat[-1] * 100
    print('마지막 매수건 수익률: ', buy_profit)

    if buy_profit < -0.5   and not ordered:
        print('매수조건 달성')
        print('ordered=True: ', ordered)

        매수할금액 = 500000
        quantity = 매수할금액 // int(df['새현재가'][0])
        buy_json_data = {'code': '233740', 'quantity': str(quantity)}
        await kis.buy_order(buy_json_data)
        ordered = True


    # 잔고테이블의 행이 1개 이상 있고, 딕셔너리가 비어 있을 때
    if (jango_df.shape[0] > 0) and not sell_to_buy_order_map:
        print('kis.__sell_to_buy_order_map', sell_to_buy_order_map)
        # 수익률 계산
        fee_rate = 0.00015
        tax_rate = 0.0015

        수량 = jango_df['체결수량'].astype('int')
        매수가 = jango_df['체결단가'].astype('int')
        현재가 = jango_df['현재가'].astype('int')

        print('수량: ', 수량.sum())
        print('매입단가: ', round(((매수가 * 수량).sum()) / 수량.sum(), 2))

        매입금액 = (매수가 * 수량).sum()
        print('매입금액: ', 매입금액)
        평가금액 = (현재가 * 수량).sum()
        print('평가금액: ', 평가금액)
        세전_수익금 = 평가금액 - 매입금액
        print('세전_수익금: ', 세전_수익금)

        매수_수수료 = 매입금액 * fee_rate
        매도_수수료 = 평가금액 * fee_rate
        세금 = 평가금액 * tax_rate
        세후_수익금 = 세전_수익금 - 매수_수수료 - 매도_수수료 - 세금
        print('세후_수익금: ', 세후_수익금)

        수익률 = 세후_수익금 / 매입금액
        수익률 = round(수익률 * 100, 2)
        print('수익률: ', '\n', 수익률, '\n')

        # print("jango_df['매도_주문번호']", jango_df['매도_주문번호'].isna().all())
        # if jango_df['매도_주문번호'].isna().all():
        # if not kis.__sell_to_buy_order_map:



        if 수익률 > 0.5:
            print('수익중..')
            # {"order_number": "2508280000001845", "stock_code": "233740", "stock_name": "KODEX 코스닥150레버리지", "quantity": "1"}}
            send_data = (jango_df[['매수_주문번호', '종목코드', '종목명', '체결수량']].
                         rename(columns={
                                '매수_주문번호': 'order_number',
                                '종목코드': 'stock_code',
                                '종목명': 'stock_name',
                                '체결수량': 'quantity'
                        }).to_dict(orient="records"))
            print('send_data', send_data)

            for json_data in send_data:
                # asyncio.create_task(kis.sell_order(json_data))
                res = await kis.sell_order(json_data)
                print('res', res)
                if 'output1' in res:
                    sell_order_no, sell_order_price, sell_order_qty = res['output1']
                    print("매도 주문 응답 정상", sell_order_no, sell_order_price, sell_order_qty)
                    jango_df.loc[jango_df['매수_주문번호'] == json_data['order_number'], ['매도_주문번호', '매도_주문가격', '매도_주문수량']] = (sell_order_no, sell_order_price, sell_order_qty)
                    json_data_html = jango_df.drop(columns='체결량').to_dict(orient="records")
                    data = {"type": "stock_data", "data": json_data_html}
                    await websocket_manager.manager.broadcast(json.dumps(data))

                print("json.dumps(res['output2'])", json.dumps(res['output2']))
                await websocket_manager.manager.broadcast(json.dumps(res['output2']))
                await asyncio.sleep(0.5)


        else:
            print('손실중...')


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
    now = datetime.now()
    time_str = now.strftime("%Y%m%d%H%M%S")

    if tr_id in ['H0STCNI9', 'H0STCNI0']:
        res = account_balance.get_balance()
        if res:
            d2_cash = int(res)

    mask = (jango_df['현재가'] == "") | (jango_df['현재가'].isna())  # 현재가가 없는 행 찾기
    if mask.any():  # 현재가가 없는 행이 하나라도 있으면 패스
        return None  # None 을 반환하고 종료
    else:           # 현재가가 모든 행에 전부 있으면
        try:
            수량 = jango_df['체결잔량'].fillna(jango_df['체결수량']).astype(int)
            매입금액 = int((수량 * jango_df['체결단가'].astype(int)).sum())
            # 매입금액 = int((jango_df['체결수량'].astype('int') * jango_df['체결단가'].astype('int')).sum())
            매입수수료 = int(매입금액 * fee_rate)
            # 평가금액 = int((jango_df['체결수량'].astype('int') * jango_df['현재가'].astype('int')).sum())
            평가금액 = int((수량 * jango_df['현재가'].astype(int)).sum())
            매도수수료 = int(평가금액 * fee_rate)
            세금 = int(평가금액 * tax_rate)
            평가금액 = 평가금액 - 매입수수료 - 매도수수료 - 세금
            balance = d2_cash + 매입금액
            print('balance: ', balance)
            tot_acc_value = d2_cash + 평가금액
            acc_profit = tot_acc_value - balance
            print('balance: ', balance)


            if tr_id in ['H0STCNI9', 'H0STCNI0']:
                jango_data = {
                    '시간': time_str,
                    '잔고': balance
                }
                print('jango_data: ', jango_data)
                kis_db.insert_data(jango_data)

            return balance, tot_acc_value, acc_profit, d2_cash



        except Exception as e:
            print('update_balance() 에러:  ', e)