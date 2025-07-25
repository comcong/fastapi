import json
import websockets
from fastapi import WebSocket as fws   #, WebSocketDisconnect
from app.kis_invesment.socket_current_price import get_stock_price
from app.kis_invesment.kis_manager import kis_api
import asyncio

connected_clients = set()   # 접속한 클라이언트 초기화
kis_task = None             # kis_receiver가 실행 중인지 추적
code_list:list[str] = ['015760', '052690', '005380', '000270', '027360' ]

# 실시간 체결알람 엔드포인트
async def endpoint(fws: fws):
    global kis_task

    await fws.accept()          # fastapi 웹소켓 연결 허용
    connected_clients.add(fws)  # 새로운 클라이언트 추가
    print("새로운 클라이언트 추가")

    # 최초 클라이언트일 경우 kis_receiver 실행
    if kis_task is None or kis_task.done():
        kis_task = asyncio.create_task(kis_transaction())

    try:
        while True:
            await fws.receive_text()  # 클라이언트 대기
    except Exception as e:
        print("클라이언트 오류:", e)
    finally:
        connected_clients.remove(fws)
        print("클라이언트 제거됨")



async def kis_transaction():
    add_url = '/tryitout/H0STCNI0'
    transaction = kis_api(add_url)

    async with websockets.connect(transaction.url) as ws:           # 체결 웹소켓 생성
        print("KIS 웹소켓에 연결됨")
        await transaction.subscribe_transaction(ws)                 # 한투API에 체결 구독신청

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


async def kis_price():
    add_url = '/tryitout/H0STCNT0'
    price = kis_api(add_url)

    async with websockets.connect(price.url) as ws:                 # 현재가 웹소켓 생성
        print("KIS 웹소켓에 연결됨")
        await price.subscribe_transaction(ws)                       # 한투API에 체결 구독신청

        while True:
            try:
                data = await ws.recv()
                print('수신 데이터: ', data)
                data = await price.make_data(data)
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


