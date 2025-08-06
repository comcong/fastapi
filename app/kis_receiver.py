# kis_receiver.py
import asyncio
import json
import pandas as pd
import websockets
import traceback

import websocket_manager
from app.db import kis_db
from app.kis_invesment.kis_manager import kis

jango_df: pd.DataFrame = pd.DataFrame()

async def start_kis_receiver():
    global jango_df
    jango_df = jango_db()
    code_list = jango_df['종목코드'].unique().tolist() # DB 에서 종목코드 가져옴
    async with websockets.connect(kis.url) as ws:
        await kis.subscribe(ws=ws)
        print('첫 code_list', code_list)
        await kis.subscribe(ws=ws, tr_id='H0STCNT0', code_list=code_list)

        while True:
            try:
                raw_data = await ws.recv()  # ws로부터 데이터 수신
                # print("수신된 원본 데이터: ")
                # print(raw_data)
                data = await kis.make_data(raw_data)  # 데이터 가공
                print("수신된 가공 데이터: ")
                print(data)

                if isinstance(data, pd.DataFrame):
                    tr_id = data.iloc[0]['tr_id']
                    if tr_id == 'H0STCNT0':  # 실시간 현재가가 들어오는 경우
                        print('tr_id == "H0STCNT0":')

                        jango_df = update_jango_df(data[['종목코드', '새현재가']].copy())
                        json_data = strip_zeros(jango_df.to_dict(orient="records"))
                        data = {"type": "stock_data", "data": json_data}
                        await websocket_manager.manager.broadcast(json.dumps(data))
                        print('데이터프레임 전송완료')

                    elif (tr_id in ['H0STCNI9', 'H0STCNI0']) and (data['체결여부'].values.tolist()[0] == '2'):  # 체결통보 데이터
                        # sanare78^5014279001^0000001562^^02^0^00^0^027360^0000000001^000002200^092701^0^1^1^00950^000000001^신명진^1Y^10^^아주IB투자^
                        trans_df = data.copy()
                        print('체결통보 df')
                        print(jango_df)
                        if trans_df['매도매수구분'].values[0] == '02':    # 01: 매도, 02: 매수
                            jango_df = await kis.buy_update(ws=ws, jango_df=jango_df, trans_df=trans_df)

                        elif trans_df['매도매수구분'].values[0] == '01':    # 01: 매도, 02: 매수
                            jango_df = kis.sell_update(jango_df=jango_df, trans_df=trans_df)


                        json_data = strip_zeros(jango_df.to_dict(orient="records"))
                        print('json_data', json_data)
                        data = {"type": "stock_data", "data": json_data}
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
    col_names = ['주문번호', '종목명', '종목코드', '체결시간', '체결수량', '체결단가', '현재가']
    jango_df = pd.DataFrame(supa_db, columns=col_names)
    return jango_df

async def send_initial_data(websocket):
    jango_json_data = jango_df.to_dict(orient="records")
    stock_data = {"type": "stock_data", "data": jango_json_data}
    await websocket.send_text(json.dumps(stock_data))

# 숫자 앞 0을 없애주는 함수
def strip_zeros(json_list: list[dict]) -> list[dict]:
    # print('strip_zeros 실행')
    # print('json_list: ', json_list)
    keys_to_strip_zeros = ['주문번호', '체결수량', '체결단가']
    for record in json_list:
        for key in keys_to_strip_zeros:
            if key in record and record[key]:
                try:
                    record[key] = str(int(record[key]))
                except (ValueError, TypeError):
                    pass  # 숫자 변환 불가능한 값은 건너뜀
    return json_list

def update_jango_df(df: pd.DataFrame = None) -> pd.DataFrame:
    # print('update_jango_df() 실행')
    # print('update_jango_df() df')
    # print(df)
    global jango_df  # 실시간 현재가 데이터 전역변수 사용
    if df is None:
        return jango_df
    else:
        print('타입비교')
        print('현재가', jango_df["현재가"])
        print('새현재가', df["새현재가"])
        jango_df = pd.merge(jango_df, df, on='종목코드', how='left')  # 병합
        print('타입비교')
        print('현재가', jango_df["현재가"])
        print('새현재가', jango_df["새현재가"])
        jango_df.loc[jango_df["새현재가"].notna(), "현재가"] = jango_df["새현재가"]
        jango_df = jango_df.drop(columns=['새현재가'])
        jango_df = jango_df[['주문번호', '종목명', '종목코드', '체결시간', '주문수량', '체결수량', '체결단가', '현재가']]
        # print('update_jango_df() jango_df')
        # print(jango_df)
        return jango_df