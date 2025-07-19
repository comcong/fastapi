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


async def current_price_endpoint():

    # 콜백 함수 정의 - get_stock_price에서 데이터를 받을 때 호출됩니다
    def data_callback(data):
        print(f"콜백을 통해 받은 데이터: {data}")

        # 여기서 받은 데이터로 추가 처리를 할 수 있습니다
        # 예: 데이터베이스 저장, 다른 서비스로 전송 등

    # get_stock_price 함수에 콜백 함수를 전달하여 실행
    await get_stock_price('005930', data_callback)

if __name__ == "__main__":
    asyncio.run(current_price_endpoint())




