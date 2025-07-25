import json
import websockets
from fastapi import WebSocket as fws
from app.kis_invesment.kis_manager import kis_api
import asyncio

connected_clients = set()
task = None
code_list = ['015760', '052690', '005380', '000270', '027360']


async def endpoint(fws: fws):
    global task

    await fws.accept()
    connected_clients.add(fws)
    print("새로운 클라이언트 추가")

    if task is None or task.done():
        task = asyncio.create_task(combined_kis_task())

    try:
        while True:
            await fws.receive_text()
    except Exception as e:
        print("클라이언트 오류:", e)
    finally:
        connected_clients.remove(fws)
        print("클라이언트 제거됨")


async def combined_kis_task():
    tr_id_price = 'H0STCNT0'
    tr_id_transaction = 'H0STCNI0'

    # 하나의 kis_api 인스턴스를 사용하되, 각 tr_id별로 따로 초기화
    price_api = kis_api(tr_id_price, code_list)
    transaction_api = kis_api(tr_id_transaction)

    async with websockets.connect(price_api.url) as ws:
        print("✅ 하나의 KIS 웹소켓에 연결됨")

        # 순차적으로 두 개 구독 요청
        await price_api.subscribe_price(ws)
        await transaction_api.subscribe_transaction(ws)

        while True:
            try:
                raw_data = await ws.recv()
                print("수신된 데이터: ", raw_data)

                # 먼저 현재가 데이터 시도
                data = await price_api.make_data(raw_data)
                if not data:
                    # 현재가로 파싱 실패 → 체결로 시도
                    data = await transaction_api.make_data(raw_data)

                if data:
                    print("가공 데이터: ", data)
                    for client in connected_clients.copy():
                        try:
                            await client.send_text(json.dumps(data, ensure_ascii=False))
                        except Exception as e:
                            print("클라이언트 전송 실패:", e)
                            connected_clients.remove(client)
                else:
                    print("알 수 없는 데이터:", raw_data)

            except Exception as e:
                print("웹소켓 수신 오류:", e)
                break
