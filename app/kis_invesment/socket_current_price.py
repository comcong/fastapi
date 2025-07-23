import websockets
import json
from app.core.config import settings
from app.services.kis_auth import get_approval_key

menulist = "유가증권단축종목코드|주식체결시간|주식현재가|전일대비부호|전일대비|전일대비율|가중평균주식가격|주식시가|주식최고가|주식최저가|매도호가1|매수호가1|체결거래량|누적거래량|누적거래대금|매도체결건수|매수체결건수|순매수체결건수|체결강도|총매도수량|총매수수량|체결구분|매수비율|전일거래량대비등락율|시가시간|시가대비구분|시가대비|최고가시간|고가대비구분|고가대비|최저가시간|저가대비구분|저가대비|영업일자|신장운영구분코드|거래정지여부|매도호가잔량|매수호가잔량|총매도호가잔량|총매수호가잔량|거래량회전율|전일동시간누적거래량|전일동시간누적거래량비율|시간구분코드|임의종료구분코드|정적VI발동기준가"

async def get_stock_price(stock_code, callback=None):
    print('====================================')
    print('get_stock_price 실행')
    print('====================================')
    approval_key = get_approval_key()

    tr_type = '1'
    tr_id = 'H0STCNT0'  # 실시간 현재가 조회

    # 서버 URL 설정 (모의/실전)
    base_url = 'ws://ops.koreainvestment.com:31000' if settings.KIS_USE_MOCK else 'ws://ops.koreainvestment.com:21000'
    url = f"{base_url}/tryitout/H0STCNT0"


    # 요청 데이터 구성
    senddata = req_data(approval_key, tr_id, stock_code, tr_type)

    try:
        async with websockets.connect(url) as ws:  # 웹소켓 연결
            print(f"한국투자증권 WebSocket 서버에 연결되었습니다: {url}")

            # 데이터 전송
            await ws.send(json.dumps(senddata))
            print(f"요청 데이터 전송 완료: {stock_code} 종목 실시간 시세 요청")

            # 데이터 수신 루프
            while True:
                try:
                    data = (await ws.recv())       # 데이터 수신 대기
                    print('최초 수신 데이터: ', data)
                    try:
                        data = json.loads(data)
                    except:
                        data = stockspurchase(data)

                    # 데이터 전송
                    if callback:
                        await callback(data)  # 비동기 콜백은 await로 호출

                except Exception as e:
                    print(f"데이터 수신 중 오류 발생: {e}")
                    break
    except Exception as e:
        print(f"웹소켓 연결 중 오류 발생: {e}")


def req_data(approval_key, tr_id, stock_code, tr_type):
    # 요청 데이터 구성
    senddata = {
        "header": {
            "approval_key": approval_key,
            "custtype": "P",
            "tr_type": tr_type,
            "content-type": "utf-8"
        },
        "body": {
            "input": {
                "tr_id": tr_id,
                "tr_key": stock_code
            }
        }
    }
    return senddata

# 주식체결처리 출력라이브러리
def stockspurchase(data):  # 주식 현재가 데이터 정제
    # data = '0|H0STCNT0|001|005930^120651^67050^5^-750^-1.11^67620.79^68100^68500^67000^67100^67000^200^8293601^560819903500^25773^26194^421^67.01^4648298^3114657^1^0.38^46.80^090008^5^-1050^090433^5^-1450^100933^2^50^20250722^20^N^122087^257541^794914^1365374^0.14^10573794^78.44^0^^68100'
    data_keys = menulist.split('|')
    data_values = data.split('|')[3].split('^')
    result = dict(zip(data_keys, data_values))   # zip으로 묶어서 딕셔너리 생성
    return result