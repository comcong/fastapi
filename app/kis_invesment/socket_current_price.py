import websockets
import asyncio
import json
from app.services.approval_key import get_approval_key
from app.core.config import settings
# from app.websocket.realtime_websocket import process_data

async def get_stock_price(stock_code='000270', callback=None):
    approval_key = get_approval_key()
    tr_id = 'H0STCNT0'  # 실시간 현재가 조회

    # 서버 URL 설정 (모의/실전)
    base_url = 'ws://ops.koreainvestment.com:31000' if settings.KIS_USE_MOCK else 'ws://ops.koreainvestment.com:21000'
    url = f"{base_url}/tryitout/H0STCNT0"

    # 요청 데이터 구성
    senddata = {
        "header": {
            "approval_key": approval_key,
            "custtype": "P",
            "tr_type": "1",
            "content-type": "utf-8"
        },
        "body": {
            "input": {
                "tr_id": tr_id,
                "tr_key": stock_code
            }
        }
    }

    try:
        async with websockets.connect(url) as ws:  # 웹소켓 연결
            print(f"한국투자증권 WebSocket 서버에 연결되었습니다: {url}")

            # 데이터 전송
            await ws.send(json.dumps(senddata))
            print(f"요청 데이터 전송 완료: {stock_code} 종목 실시간 시세 요청")

            # 데이터 수신 루프
            while True:
                try:
                    response = await ws.recv()         # 데이터 수신 대기
                    data = json.loads(response)        # JSON 파싱

                    # 데이터 전달
                    if callback:
                        callback(data)

                except Exception as e:
                    print(f"데이터 수신 중 오류 발생: {e}")
                    break
    except Exception as e:
        print(f"웹소켓 연결 중 오류 발생: {e}")






