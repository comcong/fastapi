import websockets
import json
from app.services.kis_auth import get_approval_key
from app.core.config import settings
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode

menulist = "고객ID|계좌번호|주문번호|원주문번호|매도매수구분|정정구분|주문종류|주문조건|주식단축종목코드|체결수량|체결단가|주식체결시간|거부여부|체결여부|접수여부|지점번호|주문수량|계좌명|호가조건가격|주문거래소구분|실시간체결창표시여부|필러|신용구분|신용대출일자|체결종목명40|주문가격"

async def get_transaction(HTS_ID, callback=None):
    print('====================================')
    print('get_transaction 실행')
    print('====================================')
    approval_key = get_approval_key()
    tr_type = '1'
    if settings.KIS_USE_MOCK == True:  # 모의
        base_url = "ws://ops.koreainvestment.com:31000"
        tr_id = 'H0STCNI9'
    elif settings.KIS_USE_MOCK == False: # 실전
        base_url = "ws://ops.koreainvestment.com:21000"
        tr_id = 'H0STCNI0'

    # 서버 URL 설정 (모의/실전)
    url = f"{base_url}/tryitout/H0STCNI0"


    # 요청 데이터 구성
    senddata = req_data(approval_key, tr_id, HTS_ID, tr_type)

    try:
        async with websockets.connect(url) as ws:  # 웹소켓 연결
            print(f"한국투자증권 WebSocket 서버에 연결되었습니다: {url}")

            # 데이터 전송
            await ws.send(json.dumps(senddata))
            print(f"요청 데이터 전송 완료: {HTS_ID} 실시간 체결 통보 요청")

            # 데이터 수신 루프
            while True:
                try:
                    data = (await ws.recv())       # 데이터 수신 대기
                    print('최초 수신 데이터: ', data)
                    try:
                        data = json.loads(data)
                        if 'body' in data.keys():
                            iv = data['body']['output']['iv']
                            key = data['body']['output']['key']

                    except :
                        cipher_text = data.split('|')[3]
                        print('암호데이터: ', cipher_text)
                        data = aes_cbc_base64_dec(key, iv, cipher_text)
                        print('해독데이터: ', data)


                    # 데이터 전송
                    if callback:
                        await callback(data)  # 비동기 콜백은 await로 호출

                except Exception as e:
                    print(f"데이터 수신 중 오류 발생: {e}")
                    break
    except Exception as e:
        print(f"웹소켓 연결 중 오류 발생: {e}")


def req_data(approval_key, tr_id, HTS_ID, tr_type):
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
                "tr_key": HTS_ID
            }
        }
    }
    return senddata

# AES256 DECODE
def aes_cbc_base64_dec(key, iv, cipher_text):
    cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))
    return bytes.decode(unpad(cipher.decrypt(b64decode(cipher_text)), AES.block_size))
