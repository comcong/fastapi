import random
import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect

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