import json
from app.services.kis_auth import get_approval_key
from app.core.config import settings
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode

menulist = "고객ID|계좌번호|주문번호|원주문번호|매도매수구분|정정구분|주문종류|주문조건|주식단축종목코드|체결수량|체결단가|주식체결시간|거부여부|체결여부|접수여부|지점번호|주문수량|계좌명|호가조건가격|주문거래소구분|실시간체결창표시여부|필러|신용구분|신용대출일자|체결종목명40|주문가격"
class kis_api:
    def __init__(self, tr_id, code_list=None):
        self.__approval_key = get_approval_key()
        self.__HTS_ID = settings.KIS_HTS_ID
        # self.__add_url = add_url
        self.__code_list = code_list

        if settings.KIS_USE_MOCK == True:  # 모의
            url = "ws://ops.koreainvestment.com:31000"
        elif settings.KIS_USE_MOCK == False:
            url = "ws://ops.koreainvestment.com:21000"  # 실전
        self.url = url
        self.__tr_id = tr_id

        if tr_id == 'H0STCNT0':    # 실시간 체결가
            self.__tr_key = self.__code_list
        elif (tr_id == 'H0STCNI0') or (tr_id == 'H0STCNI9'):  # 실시간 체결통보
            self.__tr_key = self.__HTS_ID


    async def subscribe_transaction(self, ws):
        print('====================================')
        print('subscribe_transaction 실행')
        print('====================================')


        tr_type = '1'                                            # 1: 등록,     2: 해제

        # 요청 데이터 구성
        senddata = self.__req_data(self.__tr_key, tr_type)
        print('체결등록 전송데이터', senddata)
        await ws.send(json.dumps(senddata))

    async def subscribe_price(self, ws):
        print('====================================')
        print('subscribe_price 실행')
        print('====================================')
        HTS_ID = settings.KIS_HTS_ID
        tr_type = '1'                                            # 1: 등록,     2: 해제

        # 요청 데이터 구성
        for tr_key in self.__code_list:
            senddata = self.__req_data(tr_key, tr_type)
            print('현재가등록 전송데이터', senddata)
            await ws.send(json.dumps(senddata))




    async def make_data(self, data):
        if (self.__tr_id == 'H0STCNI0') or (self.__tr_id == 'H0STCNI9'):    # 체결통보
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
                data = self.__aes_cbc_base64_dec(key, iv, cipher_text)
                print('해독데이터: ', data)
            return data

        elif self.__tr_id == 'H0STCNT0': # 실시간 체결가
            try:
                data = json.loads(data)
            except:
                data = self.__price_data_cleaning(data)
            return data

    def __req_data(self, tr_key, tr_type): # 구독 신청/해제

        # 요청 데이터 구성
        senddata = {
            "header": {
                "approval_key": self.__approval_key,
                "custtype": "P",
                "tr_type": tr_type,
                "content-type": "utf-8"
            },
            "body": {
                "input": {
                    "tr_id": self.__tr_id,
                    "tr_key": tr_key
                }
            }
        }
        return senddata

    # AES256 DECODE
    def __aes_cbc_base64_dec(self, key, iv, cipher_text):
        cipher = AES.new(key.encode('utf-8'), AES.MODE_CBC, iv.encode('utf-8'))
        # data = bytes.decode(unpad(cipher.decrypt(b64decode(cipher_text)), AES.block_size))
        data = unpad(cipher.decrypt(b64decode(cipher_text)), AES.block_size).decode('utf-8')
        return self.__transaction_data_cleaning(data)

    # 체결통보 출력라이브러리
    def __transaction_data_cleaning(self, data):  # 체결통보 데이터 정제
        # data = 'sanare78^5014279001^0000005008^^02^0^00^0^069500^0000000001^000043295^144700^0^2^2^00950^000000001^신명진^1Y^10^^KODEX200^000044000'
        data_keys = menulist.split('|')
        data_values = data.split('^')
        result = dict(zip(data_keys, data_values))   # zip으로 묶어서 딕셔너리 생성
        return result

    # 현재가 출력라이브러리
    def __price_data_cleaning(self, data):  # 주식 현재가 데이터 정제
        # data = '0|H0STCNT0|001|005930^120651^67050^5^-750^-1.11^67620.79^68100^68500^67000^67100^67000^200^8293601^560819903500^25773^26194^421^67.01^4648298^3114657^1^0.38^46.80^090008^5^-1050^090433^5^-1450^100933^2^50^20250722^20^N^122087^257541^794914^1365374^0.14^10573794^78.44^0^^68100'
        data_keys = menulist.split('|')
        data_values = data.split('|')[3].split('^')
        result = dict(zip(data_keys, data_values))  # zip으로 묶어서 딕셔너리 생성
        return result


    # 나중에 통합
    async def subscribe(self, ws, tr_type='1'):
        senddata = self.__req_data(tr_type)
        await ws.send(json.dumps(senddata))