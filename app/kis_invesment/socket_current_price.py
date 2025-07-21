import websockets
import asyncio
import json
from app.services.approval_key import get_approval_key
from app.core.config import settings

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
                    data = response
                    if isinstance(data, str):
                        print('문자열입니다.')
                    elif isinstance(data, dict):
                        print('딕셔너리입니다.')

                    # 콜백이 비동기 함수인지 확인하고 적절히 호출
                    if callback:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(data)  # 비동기 콜백은 await로 호출
                        else:
                            callback(data)        # 동기 콜백은 직접 호출

                except Exception as e:
                    print(f"데이터 수신 중 오류 발생: {e}")
                    break
    except Exception as e:
        print(f"웹소켓 연결 중 오류 발생: {e}")