import random
import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
from app.kis_invesment.socket_current_price import get_stock_price

async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            # 랜덤 데이터 생성
            data1 = random.uniform(0, 100)
            data2 = random.uniform(200, 300)

            message = {
                "temperature": data1,
                "humidity": data2
            }

            await websocket.send_text(json.dumps(message))

            # 1초 대기
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        print("클라이언트 연결 종료")


async def current_price_endpoint(websocket: WebSocket):
    await websocket.accept()

    # 비동기 콜백 함수로 변경
    async def data_callback(data):
        print(f"콜백을 통해 받은 데이터: {data}")
        try:
            await websocket.send_text(json.dumps(data))
        except Exception as e:
            print(f"데이터 전송 실패: {e}")

    # get_stock_price 함수에 비동기 콜백 함수를 전달하여 실행
    await get_stock_price('005930', data_callback)




