import json
import websockets
from fastapi import WebSocket, WebSocketDisconnect
from app.kis_invesment.socket_current_price import get_stock_price
from app.kis_invesment.kis_manager import kis_data
import asyncio
# from app.core.config import settings
# from app.services.kis_auth import get_approval_key

connected_clients = set()   # 접속한 클라이언트 초기화
kis_task = None  # kis_receiver가 실행 중인지 추적

# 실시간 체결알람 엔드포인트
async def transaction_endpoint(websocket: WebSocket):
    global kis_task

    await websocket.accept()
    connected_clients.add(websocket)  # 새로운 클라이언트 추가
    print("새로운 클라이언트 추가")

    # 최초 클라이언트일 경우 kis_receiver 실행
    if kis_task is None or kis_task.done():
        kis_task = asyncio.create_task(kis_receiver())

    try:
        while True:
            await websocket.receive_text()  # 클라이언트 대기
    except Exception as e:
        print("클라이언트 오류:", e)
    finally:
        connected_clients.remove(websocket)
        print("클라이언트 제거됨")


async def kis_receiver():
    url = "/tryitout/H0STCNI0"
    transaction = kis_data(url)

    async with websockets.connect(transaction.url) as ws:
        print("KIS 웹소켓에 연결됨")
        await transaction.subscribe_transaction(ws)  # 한투API에 체결 구독신청

        while True:
            try:
                data = await ws.recv()
                print('수신 데이터: ', data)
                data = await transaction.make_data(data)
                print('가공 데이터: ', data)

                # 연결된 모든 클라이언트에게 전송
                for client in connected_clients:
                    try:
                        await client.send_text(json.dumps(data, ensure_ascii=False))
                    except Exception as e:
                        print("클라이언트 전송 실패:", e)
                        connected_clients.remove(client)

            except Exception as e:
                print("KIS 웹소켓 오류:", e)





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