import asyncio
import json
import pandas as pd

import websocket_manager
from app.db import kis_db

# 여기를 실제 한투 API WebSocket 수신으로 교체 가능
async def start_kis_receiver():
    jango_df = jango_db()

    while True:
        await asyncio.sleep(1)  # 1초마다 수신한다고 가정
        print("화일문 실행중")
        if jango_df.empty:
            # 비어 있어도 컬럼 정보는 포함되도록
            json_data = [{col: "" for col in jango_df.columns}]
        else:
            json_data = jango_df.to_dict(orient="records")
        # json_data = jango_df.to_dict(orient="records")
        print(json_data)

        data = {"type": "stock_data", "data": json_data}
        await websocket_manager.manager.broadcast(json.dumps(data)) #, ensure_ascii=False)


def jango_db():
    supa_db = kis_db.get_data()
    col_names = ['주문번호', '종목명', '종목코드', '체결시간', '체결수량', '체결단가', '현재가']
    if supa_db:
        jango_df = pd.DataFrame(supa_db)
        jango_df = jango_df[['주문번호', '종목명', '종목코드', '체결시간', '체결수량', '체결단가', '현재가']].sort_values('주문번호')
    elif not supa_db:
        jango_df = pd.DataFrame(supa_db, columns=col_names)
    return jango_df