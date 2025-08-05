import asyncio
import json
import pandas as pd
import websockets
import traceback

import websocket_manager
from app.db import kis_db
from app.kis_invesment.kis_manager import kis

jango_df: pd.DataFrame = pd.DataFrame()
# code_list: list = []

# 여기를 실제 한투 API WebSocket 수신으로 교체 가능
async def start_kis_receiver():
    global jango_df
    # global code_list
    jango_df = jango_db()
    code_list = jango_df['종목코드'].unique().tolist() # DB 에서 종목코드 가져옴
    async with websockets.connect(kis.url) as ws:
        await kis.subscribe(ws=ws)
        await kis.subscribe(ws=ws, tr_id='H0STCNT0', code_list=code_list)

    while True:
        try:
            await asyncio.sleep(1)
            print("화일문 1")
            raw_data = await ws.recv()  # ws로부터 데이터 수신
            print("화일문 2")
            print("수신된 원본 데이터: ")
            print(raw_data)

            data = await kis.make_data(raw_data)  # 데이터 가공
            print("수신된 가공 데이터: ")
            print(data)

            if isinstance(data, pd.DataFrame):
                json_data = data.to_dict(orient="records")
                data = {"type": "stock_data", "data": json_data}
                await websocket_manager.manager.broadcast(json.dumps(data))
                print('데이터프레임 전송완료')

            else:
                json_data = data
                data = {"type": "message", "data": json_data}
                await websocket_manager.manager.broadcast(data)
                print('json 전송완료')



        except Exception as e:
            print("웹소켓 수신 오류: 1", e)
            traceback.print_exc()





def jango_db():
    supa_db = kis_db.get_data()
    col_names = ['주문번호', '종목명', '종목코드', '체결시간', '체결수량', '체결단가', '현재가']
    jango_df = pd.DataFrame(supa_db, columns=col_names)
    return jango_df