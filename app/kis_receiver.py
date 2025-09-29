# kis_receiver.py
import asyncio
import json
import pandas as pd
import websockets
from datetime import datetime
import traceback
import requests

import websocket_manager
from app.core.config import settings
from app.db import kis_db
from app.kis_invesment.kis_manager import kis
from app.kis_invesment import account_balance
from app.services import kis_auth

jango_df = pd.DataFrame()
d2_cash = int(account_balance.get_balance())
ordered = False
sell_to_buy_order_map = {}
# yymmdd = datetime.now().strftime("%y%m%d")
async def start_kis_receiver():
    global jango_df
    global ordered
    jango_df = jango_db(settings.col_names)
    print('jango_df_1', '\n', jango_df.shape)
    # code_list = jango_df['종목코드'].unique().tolist()  # DB 에서 종목코드 가져옴
    code_list = ['233740']

    while True:
        try:
            async with websockets.connect(settings.ws_url) as ws:
                await kis.subscribe(ws=ws)
                await kis.subscribe(ws=ws, tr_id='H0STCNT0', code_list=code_list)

                while True:
                    raw_data = await ws.recv()
                    data = await kis.make_data(raw_data)  # 데이터 가공

                    if isinstance(data, pd.DataFrame):
                        print("수신된 가공 데이터: ")
                        print(data.columns)
                        tr_id = data.iloc[0]['tr_id']
                        if tr_id == 'H0STCNT0':            # 실시간 현재가가 들어오는 경우
                            print('실시간 현재가 수신')
                            jango_df = await update_price(data[['종목코드', '새현재가']].copy())
                            print('jango_df_2', '\n', jango_df.shape)
                            await send_update_balance()

                        elif (tr_id in ['H0STCNI9', 'H0STCNI0']) and (data['체결여부'].values.tolist()[0] == '2'):  # 체결통보 데이터
                            print('실시간 체결통보 수신')
                            trans_df = data.copy()

                            if trans_df['매도매수구분'].values[0] == '02':  # 매수       # 01: 매도, 02: 매수
                                print('매수 체결통보')
                                jango_df = await buy_update(ws=ws, jango_df=jango_df, trans_df=trans_df)
                                print('jango_df_3', '\n', jango_df.shape)
                                await send_update_balance(tr_id=tr_id, order_type='매수')

                            elif trans_df['매도매수구분'].values[0] == '01': # 매도      # 01: 매도, 02: 매수
                                print('매도 체결통보')
                                print('체결수량:  ', trans_df.at[0, '체결수량'])
                                jango_df = await sell_update(ws=ws, jango_df=jango_df, trans_df=trans_df)
                                print('jango_df_4', '\n', jango_df.shape)
                                await send_update_balance(tr_id=tr_id, order_type='매도')

                            data['새현재가'] = data['체결단가']
                            jango_df = await update_price(data[['종목코드', '새현재가']].copy())
                            # asyncio.create_task(send_update_balance(tr_id))  # 백그라운드로 send_update_balance() 실행
                            if jango_df.iloc[-1]["주문수량"] == jango_df.iloc[-1]["체결수량"]:
                                ordered = False


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
            # print("start_kis_receiver 예외:", e)
            # print("예외 시점 jango_df.shape:", jango_df.shape)
            traceback.print_exc()
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


    #####  수익률 계산 ###############################
    if jango_df.shape[0] > 0:
        fee = 0.00015
        tax = 0.0015
        현재가 = int(jango_df['현재가'].iat[-1])
        체결단가 = int(jango_df['체결단가'].iat[-1])
        buy_cost = 체결단가 * (1 + fee)
        sell_income = 현재가 * (1 - (fee + tax))

        profit_rate = (sell_income - buy_cost) / buy_cost * 100
        print(f"수익률: {profit_rate:.2f}%")

    else:
        profit_rate = 0

    print('ordered: ', ordered)
    ###############  매수 조건 ###########################################
    # 매수 조건 판단
    buy_cond = (not ordered) and (
            jango_df.empty
            or (profit_rate < -0.5 and jango_df.iloc[-1]['주문수량'] == jango_df.iloc[-1]['체결수량'])
    )

    if buy_cond:
        print('매수조건_달성')
        print('ordered: ', ordered)

        매수할금액 = 500_000
        quantity = 매수할금액 // int(df['새현재가'][0])
        buy_json_data = {'code': '233740', 'quantity': str(quantity)}
        ordered = True
        await buy_order(buy_json_data)


    ###############  매도 조건 ###########################################
    # 잔고테이블의 행이 1개 이상 있고, 딕셔너리가 비어 있을 때
    if all([
        not sell_to_buy_order_map,
        profit_rate > 0.5,
        jango_df['체결잔량'].isna().all(),
        not ordered
    ]):
        print('매도조건_달성')
        print('ordered: ', ordered)
        print('sell_to_buy_order_map', sell_to_buy_order_map)
        # {"order_number": "2508280000001845", "stock_code": "233740", "stock_name": "KODEX 코스닥150레버리지", "quantity": "1"}}
        # send_data = (jango_df[['매수_주문번호', '종목코드', '종목명', '체결수량']].
        send_data = (
            jango_df[['매수_주문번호', '종목코드', '종목명', '체결수량']]
            .iloc[-1]  # Series 반환
            .rename({
                '매수_주문번호': 'order_number',
                '종목코드': 'stock_code',
                '종목명': 'stock_name',
                '체결수량': 'quantity'
            })
            .to_dict()
        )
        print('send_data', send_data)

        ordered = True
        res = await sell_order(send_data)
        print('res', res)
        if 'output1' in res:
            sell_order_no, sell_order_price, sell_order_qty = res['output1']
            print("매도 주문 응답 정상", sell_order_no, sell_order_price, sell_order_qty)
            jango_df.loc[jango_df['매수_주문번호'] == send_data['order_number'], ['매도_주문번호', '매도_주문가격', '매도_주문수량']] = (sell_order_no, sell_order_price, sell_order_qty)
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

async def send_update_balance(tr_id='', order_type=''):
    data = await update_balance(tr_id, order_type)
    if data:
        data = {'balance': data[0], 'tot_acc_value': data[1], 'acc_profit': data[2], 'd2_cash': data[3]}
        balance_data = {"type": "balance", "data": data}
        await websocket_manager.manager.broadcast(json.dumps(balance_data))

async def update_balance(tr_id='', order_type=''):
    print('update_balance() 실행')
    global d2_cash
    fee_rate = 0.00015
    tax_rate = 0.0015
    now = datetime.now()
    time_str = now.strftime("%Y년%m월%d일 %H시%M분%S초")

    if tr_id in ['H0STCNI9', 'H0STCNI0']:
        res = account_balance.get_balance()
        if res:
            d2_cash = int(res)

    mask = (jango_df['현재가'] == "") | (jango_df['현재가'].isna())  # 현재가가 없는 행 찾기
    if mask.any():  # 현재가가 없는 행이 하나라도 있으면 패스
        return None  # None 을 반환하고 종료
    else:           # 현재가가 모든 행에 전부 있으면
        # try:
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


        if (tr_id in ['H0STCNI9', 'H0STCNI0']) and (jango_df.iloc[-1]["주문수량"] == jango_df.iloc[-1]["체결수량"]):
            jango_data = {
                '시간': time_str,
                '잔고': balance,
                '주문유형': order_type,
                '주문수량': jango_df.iloc[-1]["주문수량"],
                '체결수량': jango_df.iloc[-1]["체결수량"],
                '매수_주문번호': jango_df.iloc[-1]["매수_주문번호"],
            }
            print('jango_data: ', jango_data)
            kis_db.insert_data(jango_data)

        return balance, tot_acc_value, acc_profit, d2_cash


async def sell_order(json_data):
    print('sell_stock 실행')
    global ordered
    global sell_to_buy_order_map
    try:
        # {"order_number":"3444","stock_code":"233740","stock_name":"KODEX 코스닥150레버리지","quantity":"1","current_price":"9065"}
        buy_order_no = json_data.get("order_number")
        url = f"{settings.rest_url}/uapi/domestic-stock/v1/trading/order-cash"
        code = json_data['stock_code']
        order_type = '01'
        qty = json_data['quantity']
        # price = json_data['current_price']
        price = '0'

        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {kis_auth.get_access_token()}",
            "appkey": settings.KIS_APPKEY,
            "appsecret": settings.KIS_APPSECRET,
            "tr_id": settings.tr_id_sell_order,
            "custtype": "P"
        }

        body = {
            "CANO": settings.KIS_CANO,  # 계좌번호 앞 8자리
            "ACNT_PRDT_CD": settings.KIS_ACNT_PRDT_CD,  # 계좌상품코드(뒤 2자리)
            "PDNO": code,  # 종목코드
            "ORD_DVSN": order_type,  # 00: 지정가, 03: 시장가
            "ORD_QTY": qty,  # 수량
            "ORD_UNPR": price,  # 주문단가 (시장가면 '0')
        }

        res_data = requests.post(url, headers=headers, data=json.dumps(body)).json()
        print('res_data', res_data)

        if res_data.get("rt_cd") == "0":
            print(f"[매도 주문 성공] {code} {qty}주 @ {price}원")
            output = res_data.get("output")
            sell_order_no = output.get("ODNO")  # 매도 주문번호 받아오기
            sell_to_buy_order_map[sell_order_no] = buy_order_no  # {매도주문번호 : 매수주문번호} 맵핑
            output1 = [sell_order_no, price, qty]
            output2 = {
                "type": "sell_result",
                "data": {
                    "order_number": json_data["order_number"],
                    "success": True,
                    "message": "매도 주문이 정상적으로 체결되었습니다."
                }
            }
            return {'output1': output1, 'output2': output2}

        else:
            print(f"[매도 주문 실패] {res_data}")
            output2 = {
                "type": "sell_result",
                "data": {
                    "order_number": json_data["order_number"],
                    "success": False,
                    "message": "매도 주문에 실패했습니다. 잔고를 확인하세요."
                }
            }
            return {'output2': output2}



    except Exception as e:
        print("[매도 주문 오류]", e)
        return None

async def buy_order(json_data):
    print('buy_order() 실행')
    global ordered
    url = f"{settings.rest_url}/uapi/domestic-stock/v1/trading/order-cash"
    code = json_data['code']
    order_type = '01'
    qty = json_data['quantity']
    price = '0'
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {kis_auth.get_access_token()}",
        "appkey": settings.KIS_APPKEY,
        "appsecret": settings.KIS_APPSECRET,
        "tr_id": settings.tr_id_buy_order,
        "custtype": "P"
    }

    body = {
        "CANO": settings.KIS_CANO,  # 계좌번호 앞 8자리
        "ACNT_PRDT_CD": settings.KIS_ACNT_PRDT_CD,  # 계좌상품코드(뒤 2자리)
        "PDNO": code,  # 종목코드
        "ORD_DVSN": order_type,  # 00: 지정가, 03: 시장가
        "ORD_QTY": qty,  # 수량
        "ORD_UNPR": price,  # 주문단가 (시장가면 '0')
    }

    res_data = requests.post(url, headers=headers, data=json.dumps(body)).json()
    print('res_data', res_data)


async def buy_update(ws, jango_df, trans_df):
    print('buy_update() 실행')
    yymmdd = datetime.now().strftime("%y%m%d")
    ord_num = yymmdd + trans_df['주문번호'].values[0]

    # 주문번호가 이미 존재하는지 확인
    if ord_num in jango_df['매수_주문번호'].values:
        print('주문번호가 있는 경우')
        idx = jango_df[jango_df['매수_주문번호'] == ord_num].index[0] # 기존 주문번호가 있는 행번호 가져오기

        # 수량 누적 (int로 변환 주의)
        기존_수량 = int(jango_df.at[idx, '체결수량'])
        print('기존수량: ', 기존_수량)
        신규_수량 = int(trans_df['체결수량'].values[0])
        print('신규_수량: ', 신규_수량)
        jango_df.at[idx, '체결수량'] = str(기존_수량 + 신규_수량)

        # 체결단가는 최신값으로 갱신
        기존_체결단가 = int(jango_df.at[idx, '체결단가'])
        print('기존_체결단가: ', 기존_체결단가)
        신규_체결단가 = int(trans_df['체결단가'].values[0])
        print('신규_체결단가: ', 신규_체결단가)
        평균_체결단가 = (기존_수량 * 기존_체결단가 + 신규_수량 * 신규_체결단가) / (기존_수량 + 신규_수량)
        평균_체결단가 = round(평균_체결단가)
        print('평균_체결단가')
        print(평균_체결단가)

        jango_df.at[idx, '체결단가'] = 평균_체결단가
        체결시간 = yymmdd + trans_df['체결시간'].values[0]
        jango_df.at[idx, '체결시간'] = 체결시간
        print('buy_update() 기존 주문이 있는 경우 실행 완료')

    else:  # 새로운 주문번호라면, 새로운 행에 추가
        print('주문번호가 없는 경우')
        체결시간 = yymmdd + trans_df['체결시간'].values[0]
        trans_df['체결시간'] = 체결시간

        tr_id = 'H0STCNT0'
        tran_code = trans_df['종목코드'].values[0]
        code_list = jango_df['종목코드'].unique().tolist()
        print('tran_code', tran_code)
        print('code_list', code_list)
        if tran_code not in code_list:  # 새로운 종목 구독 추가
            print('새로운 종목코드 구독 추가')
            await kis.subscribe(ws=ws, tr_type='1', tr_id=tr_id, code_list=[tran_code])
        jango_df = pd.concat([jango_df, trans_df], ignore_index=True)
        jango_df = jango_df[settings.col_names].where(pd.notna(jango_df), None)  # nan 을 None 으로 변환

        print('buy_update() 주문이 없는 경우 실행 완료')
        return jango_df


async def sell_update(ws, jango_df, trans_df):
    print('sell_update() 실행')
    global sell_to_buy_order_map
    global ordered
    print(trans_df)
    sell_ord_num = trans_df['주문번호'].values[0]
    print('sell_to_buy_order_map', sell_to_buy_order_map)
    print(len(sell_to_buy_order_map), ': 개')

    print('sell_ord_num', sell_ord_num)

    if sell_ord_num in sell_to_buy_order_map:
        buy_ord_num = sell_to_buy_order_map[sell_ord_num]
        if buy_ord_num in jango_df['매수_주문번호'].values:  # 주문번호가 존재하는지 확인
            idx = jango_df[jango_df['매수_주문번호'] == buy_ord_num].index[0] # 기존 주문번호가 있는 행번호 가져오기
            주문수량 = int(jango_df.at[idx, '매도_주문수량'])  # 에러발생
            # start_kis_receiver 예외: int() argument must be a string, a bytes - like object or a real number, not 'NoneType'

            print('주문수량', 주문수량)
            체결수량 = int(trans_df['체결수량'][0])
            print('체결수량', 체결수량)

            if jango_df.at[idx, '체결량'] in ['', None]:
                누적체결량 = 0
            else:
                누적체결량 = int(jango_df.at[idx, '체결량'])
            누적체결량 += 체결수량
            잔량 = 주문수량 - 누적체결량
            print('잔량', 잔량)
            jango_df.at[idx, '체결잔량'] = str(잔량)
            jango_df.at[idx, '체결량'] = str(누적체결량)

            if 누적체결량 == 주문수량:  # 전부 체결되면 행 제거
                print('전부체결')
                jango_df.drop(index=idx, inplace=True)
                del sell_to_buy_order_map[sell_ord_num]  # 매도 완료된 오더주문번호 삭제
                tran_code = trans_df['종목코드'].values[0]
                code_list = jango_df['종목코드'].unique().tolist()
                tr_id = 'H0STCNT0'
                print('tran_code', tran_code)
                print('code_list', code_list)
                if tran_code not in code_list:  # 없는 종목코드 구독 해제
                    print('없는 종목코드 구독 해제')
                    await kis.subscribe(ws=ws, tr_type='2', tr_id=tr_id, code_list=[tran_code])
                return jango_df

            else:
                return jango_df

    else:
        print(f"매수 주문번호가 없는 매도주문번호 {sell_ord_num} 가 체결되었습니다. 체결 데이터 확인 필요!!")
        return jango_df



        # except Exception as e:
        #     print('update_balance() 에러:  ', e)