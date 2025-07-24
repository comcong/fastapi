import json
from app.services.kis_auth import get_approval_key
from app.core.config import settings
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode

menulist = "고객ID|계좌번호|주문번호|원주문번호|매도매수구분|정정구분|주문종류|주문조건|주식단축종목코드|체결수량|체결단가|주식체결시간|거부여부|체결여부|접수여부|지점번호|주문수량|계좌명|호가조건가격|주문거래소구분|실시간체결창표시여부|필러|신용구분|신용대출일자|체결종목명40|주문가격"
class kis_data:
    def __init__(self, add_url):
        if settings.KIS_USE_MOCK == True:  # 모의
            base_url = "ws://ops.koreainvestment.com:31000"
            self.tr_id = 'H0STCNI9'
        elif settings.KIS_USE_MOCK == False:
            base_url = "ws://ops.koreainvestment.com:21000"  # 실전
            self.tr_id = 'H0STCNI0'
        self.url = base_url + add_url

    async def subscribe_transaction(self, ws):
        print('====================================')
        print('subscribe_transaction 실행')
        print('====================================')
        approval_key = get_approval_key()
        HTS_ID = settings.KIS_HTS_ID
        tr_type = '1'                                            # 1: 등록,     2: 해제

        # 요청 데이터 구성
        senddata = req_data(approval_key, self.tr_id, HTS_ID, tr_type)
        await ws.send(json.dumps(senddata))


    async def make_data(self, data):
        try:
            data = json.loads(data)
            if 'body' in data and 'output' in data['body']:
                iv = data['body']['output']['iv']
                key = data['body']['output']['key']
            else:
                pass

        except :
            cipher_text = data.split('|')[3]
            print('암호데이터: ', cipher_text)
            data = aes_cbc_base64_dec(key, iv, cipher_text)
            print('해독데이터: ', data)
        return data

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
    # data = bytes.decode(unpad(cipher.decrypt(b64decode(cipher_text)), AES.block_size))
    data = unpad(cipher.decrypt(b64decode(cipher_text)), AES.block_size).decode('utf-8')
    return stockspurchase(data)

# 체결 통보 출력라이브러리
def stockspurchase(data):  # 체결통보 데이터 정제
    # data = 'sanare78^5014279001^0000005008^^02^0^00^0^069500^0000000001^000043295^144700^0^2^2^00950^000000001^신명진^1Y^10^^KODEX200^000044000'
    data_keys = menulist.split('|')
    data_values = data.split('^')
    result = dict(zip(data_keys, data_values))   # zip으로 묶어서 딕셔너리 생성
    return result