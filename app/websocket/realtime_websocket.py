import json
import websockets
from fastapi import WebSocket as fws   #, WebSocketDisconnect
from app.kis_invesment.socket_current_price import get_stock_price
from app.kis_invesment.kis_manager import kis_api
import asyncio
import time
connected_clients = set()   # 접속한 클라이언트 초기화
task = None             # kis_transaction, kis_price 실행 중인지 추적
code_list:list[str] = ['015760', '052690', '005380', '000270', '027360' ]

# 실시간 체결알람 엔드포인트
async def endpoint(fws: fws):
    global task

    await fws.accept()          # fastapi 웹소켓 연결 허용
    connected_clients.add(fws)  # 새로운 클라이언트 추가
    print("새로운 클라이언트 추가")

    # 최초 클라이언트일 경우 kis_transaction, kis_price  실행
    if task is None or task.done():
        task = asyncio.create_task(combined_kis_task())

    try:
        while True:
            await fws.receive_text()  # 클라이언트 대기
    except Exception as e:
        print("클라이언트 오류:", e)
    finally:
        connected_clients.remove(fws)
        print("클라이언트 제거됨")



async def kis_transaction():
    # add_url = '/tryitout/H0STCNI0'
    tr_id = 'H0STCNI0'
    transaction = kis_api(tr_id)

    async with websockets.connect(transaction.url) as ws:           # 체결 웹소켓 생성
        print("KIS 웹소켓에 연결됨")
        await transaction.subscribe_transaction(ws)                 # 한투API에 체결 구독신청

        while True:
            try:
                # time.sleep(0.5)
                data = await ws.recv()
                print('체결구독 수신 데이터: ', data)
                data = await transaction.make_data(data)
                print('체결구독 가공 데이터: ', data)

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
    tr_id = 'H0STCNT0'
    price = kis_api(tr_id, code_list)

    async with websockets.connect(price.url) as ws:                 # 현재가 웹소켓 생성
        print("KIS 웹소켓에 연결됨")
        await price.subscribe_price(ws)                       # 한투API에 체결 구독신청

        while True:
            try:
                # time.sleep(0.5)
                data = await ws.recv()
                print('현재가 구독 수신 데이터: ', data)
                data = await price.make_data(data)
                print('현재가 구독 가공 데이터: ', data)

                # 연결된 모든 클라이언트에게 전송
                for client in connected_clients:
                    try:
                        await client.send_text(json.dumps(data, ensure_ascii=False))
                    except Exception as e:
                        print("클라이언트 전송 실패:", e)
                        connected_clients.remove(client)

            except Exception as e:
                print("KIS 웹소켓 오류:", e)


async def combined_kis_task():
    await asyncio.gather(
        kis_transaction(),
        kis_price()
    )