import json
from app.services.kis_auth import get_approval_key
from app.core.config import settings
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode
from app.db import kis_db
import pandas as pd



class kis_api:
    def __init__(self):
        self.__approval_key = get_approval_key()
        self.__HTS_ID = settings.KIS_HTS_ID
        self.__iv = None
        self.__key = None
        self.__price_menulist = '종목코드|체결시간|현재가|전일대비부호|전일대비|전일대비율|가중평균주식가격|시가|최고가|최저가|매도호가1|매수호가1|체결거래량|누적거래량|누적거래대금|매도체결건수|매수체결건수|순매수체결건수|체결강도|총매도수량|총매수수량|체결구분|매수비율|전일거래량대비등락율|시가시간|시가대비구분|시가대비|최고가시간|고가대비구분|고가대비|최저가시간|저가대비구분|저가대비|영업일자|신장운영구분코드|거래정지여부|매도호가잔량|매수호가잔량|총매도호가잔량|총매수호가잔량|거래량회전율|전일동시간누적거래량|전일동시간누적거래량비율|시간구분코드|임의종료구분코드|정적VI발동기준가'
        self.__trans_menulist = '고객ID|계좌번호|주문번호|원주문번호|매도매수구분|정정구분|주문종류|주문조건|종목코드|체결수량|체결단가|체결시간|거부여부|체결여부|접수여부|지점번호|주문수량|계좌명|호가조건가격|주문거래소구분|실시간체결창표시여부|필러|신용구분|신용대출일자|체결종목명40|주문가격'
        self.__df = pd.DataFrame(kis_db.get_data())

        if settings.KIS_USE_MOCK == True:  # 모의
            self.url = "ws://ops.koreainvestment.com:31000"  # ws 모의계좌
        elif settings.KIS_USE_MOCK == False:
            self.url = "ws://ops.koreainvestment.com:21000"  # ws 실전계좌


    async def subscribe(self, ws, tr_id, tr_type='1', code_list=None):
        print('====================================')
        print('kis_api.subscribe 함수 실행')
        print('====================================')


        if tr_id in ['H0STCNI0', 'H0STCNI9']:                                               # 실시간 체결알람 tr_id
            senddata = self.__req_data(tr_id=tr_id, tr_key=self.__HTS_ID, tr_type=tr_type)  # ws 에 전송할 데이터 포맷
            await ws.send(json.dumps(senddata))                                             # 실시간 체결알람 한투api에 구독 등록 요청
            print('실시간 체결알람 등록 데이터 전송', senddata)

        if tr_id == 'H0STCNT0':                                                              # 실시간 현재가 tr_id
            for tr_key in code_list:                                                         # 종목코드 순차적으로 ws 에 데이터 전송
                senddata = self.__req_data(tr_id=tr_id, tr_key=tr_key, tr_type=tr_type)
                await ws.send(json.dumps(senddata))                                          # 실시간 현재가 한투api에 구독 등록 요청
                print('실시간 현재가 등록 데이터 전송', senddata)

    def __req_data(self, tr_id  ,tr_key, tr_type):                    # ws에 전송할 데이터 포맷

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
                    "tr_id": tr_id,
                    "tr_key": tr_key
                }
            }
        }
        return senddata

    async def make_data(self, row_data):
        try:                                             # 문자열이 '|' 로 구분된 문자열인 경우
            listed_data = row_data.split('|')
            encrypted = listed_data[0]
            tr_id = listed_data[1]
            len_data =listed_data[2]
            data = listed_data[3]
            if encrypted == '1':        # 암호화된 데이터인 경우
                data = self.__aes_cbc_base64_dec(data)  # 데이터 복호화

            # 데이터를 딕셔너리 형태로 포장
            extracted_data = {
                'tr_id': tr_id,
                'len_data': len_data,
                'data': data
            }

            if (extracted_data['tr_id'] == 'H0STCNI0') or (extracted_data['tr_id'] == 'H0STCNI9'):  # 실시간 체결통보
                data_keys = self.__trans_menulist.split('|')
                data_values = data.split('^')
                data = dict(zip(data_keys, data_values))  # zip으로 묶어서 딕셔너리 형태로 변환
                data['tr_id'] = extracted_data['tr_id']   # data 에 tr_id 값 추가; 데이터 종류 구분하기 위해
                if data['매도매수구분'] == '02':  # 01: 매도, 02: 매수
                    self.__df = pd.concat([self.__df, data], ignore_index=True)    # 체결알람 데이터 데이터프레임에 한 행 추가
                    kis_db.insert_data(data)                                           # 체결알람 데이터 supabase DB에 한 행 추가
                elif data['매도매수구분'] == '01':  # 01: 매도, 02: 매수
                    self.__df = self.__df.loc[self.__df['주문번호'] != data['주문번호']]  # 매도한 주문번호 행 데이터 데이터프레임 에서 삭제
                    kis_db.delete_data(data['주문번호'])   # 매도한 주문번호 행 supabase DB 에서 삭제
                print(self.__df)
                return data  # 완성된 체결통보 데이터 df 로 리턴


            elif extracted_data['tr_id'] == 'H0STCNT0':    # 실시간 현재가
                data_keys = self.__price_menulist.split('|')
                data_values = data.split('^')
                data = dict(zip(data_keys, data_values))  # zip으로 묶어서 딕셔너리 형태로 변환
                data['tr_id'] = extracted_data['tr_id']   # data 에 tr_id 값 추가; 데이터 종류 구분하기 위해
                df = pd.DataFrame(data)
                return df   # 완성된 현재가 데이터 df 로 리턴

        except:                                                   # 딕셔너리 형태의 문자열인 경우
            data = json.loads(row_data)
            tr_id = data['header']['tr_id']
            if tr_id != 'PINGPONG':                               # PINGPONG 데이터가 아닌 경우
                rt_cd = data['body']['rt_cd']

                if rt_cd == '0':                                  # 정상 데이터인 경우
                    self.__iv = data["body"]["output"]["iv"]      # iv 값 할당
                    self.__key = data["body"]["output"]["key"]    # key 값 할당
                    msg = data["body"]["msg1"]
                    msg_cd = data["body"]["msg_cd"]
                    return data  # 정상 데이터 리턴
                else:
                    return data  # 비정상 데이터 리턴

            else:
                return data   # PINGPONG 데이터 그대로 리턴

    # AES256 DECODE
    def __aes_cbc_base64_dec(self, cipher_text):
        cipher = AES.new(self.__key.encode('utf-8'), AES.MODE_CBC, self.__iv.encode('utf-8'))
        # data = bytes.decode(unpad(cipher.decrypt(b64decode(cipher_text)), AES.block_size))
        data = unpad(cipher.decrypt(b64decode(cipher_text)), AES.block_size).decode('utf-8')
        return data