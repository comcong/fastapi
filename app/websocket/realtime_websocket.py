import json
from fastapi import WebSocket, WebSocketDisconnect
from app.kis_invesment.socket_current_price import get_stock_price

async def current_price_endpoint(websocket: WebSocket):
    await websocket.accept()

    # 비동기 콜백 함수로 변경
    async def data_callback(data):
        print(f"콜백을 통해 받은 데이터: {data}")
        if type(data) == dict:
            await websocket.send_text(json.dumps(data))
        elif type(data) == str:
            await websocket.send_text(data)

    # get_stock_price 함수에 비동기 콜백 함수를 전달하여 실행
    await get_stock_price('005930', data_callback)




