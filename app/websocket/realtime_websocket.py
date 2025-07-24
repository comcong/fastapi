import json
import websockets
from fastapi import WebSocket, WebSocketDisconnect
from app.kis_invesment.socket_current_price import get_stock_price
from app.kis_invesment.socket_transaction import data_manager

from app.core.config import settings
from app.services.kis_auth import get_approval_key

# if settings.KIS_USE_MOCK == True:  # 모의
#     base_url = "ws://ops.koreainvestment.com:31000"
#     tr_id = 'H0STCNI9'
# elif settings.KIS_USE_MOCK == False:  # 실전
#     base_url = "ws://ops.koreainvestment.com:21000"
#     tr_id = 'H0STCNI0'
# approval_key = get_approval_key()

transation_url = "/tryitout/H0STCNI0"
transation = data_manager(transation_url)


connected_transaction:bool = False


async def current_price_endpoint(websocket: WebSocket):
    await websocket.accept()

    # 비동기 콜백 함수로 변경
    async def data_callback(data):
        print(f"콜백을 통해 받은 데이터: {data}")
        if type(data) == dict:
            await websocket.send_text(json.dumps(data , ensure_ascii=False))
        elif type(data) == str:
            await websocket.send_text(data)

    # get_stock_price 함수에 비동기 콜백 함수를 전달하여 실행
    await get_stock_price(data_callback)

# 실시간 체결알람 엔드포인트
async def transaction_endpoint(websocket: WebSocket):
    global connected_transaction
    await websocket.accept()


    if connected_transaction is False:
        async with websockets.connect(transation.url) as ws:      # 실시간 체결알람 웹소켓에 연결
            print(f"실시간 체결알람 웹소켓에 연결됨")
            await subscribe_transaction(ws)                       # 실시간 체결알람 웹소켓에 체결알람 구독 신청
            connected_transaction = True

            while True:
                try:
                    data = (await ws.recv())  # 데이터 수신 대기
                    print('최초 수신 데이터: ', data)
                except:
                    pass


