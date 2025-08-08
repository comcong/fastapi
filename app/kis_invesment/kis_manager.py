import json
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode
import pandas as pd
from datetime import datetime

from app.services import kis_auth
from app.core.config import settings

class kis_api:
    def __init__(self):
        self.__approval_key = kis_auth.get_approval_key()
        self.__access_token = kis_auth.get_access_token()
        self.__HTS_ID = settings.KIS_HTS_ID
        self.__iv = None
        self.__key = None
        self.__price_menulist = '종목코드|체결시간|새현재가|전일대비부호|전일대비|전일대비율|가중평균주식가격|시가|최고가|최저가|매도호가1|매수호가1|체결거래량|누적거래량|누적거래대금|매도체결건수|매수체결건수|순매수체결건수|체결강도|총매도수량|총매수수량|체결구분|매수비율|전일거래량대비등락율|시가시간|시가대비구분|시가대비|최고가시간|고가대비구분|고가대비|최저가시간|저가대비구분|저가대비|영업일자|신장운영구분코드|거래정지여부|매도호가잔량|매수호가잔량|총매도호가잔량|총매수호가잔량|거래량회전율|전일동시간누적거래량|전일동시간누적거래량비율|시간구분코드|임의종료구분코드|정적VI발동기준가'
        self.__trans_menulist = '고객ID|계좌번호|주문번호|원주문번호|매도매수구분|정정구분|주문종류|주문조건|종목코드|체결수량|체결단가|체결시간|거부여부|체결여부|접수여부|지점번호|주문수량|계좌명|호가조건가격|주문거래소구분|실시간체결창표시여부|종목명|필러'
        self.url = settings.url


    # ============================================================= #
    # ================== 데이터 가공하는 부분 ======================== #
    # ============================================================= #

    async def make_data(self, row_data):
        try:                                             # 문자열이 '|' 로 구분된 문자열인 경우
            listed_data = row_data.split('|')
            encrypted = listed_data[0]
            tr_id = listed_data[1]
            len_data =listed_data[2]
            data = listed_data[3]

            # 데이터를 딕셔너리 형태로 포장
            extracted_data = {
                'encrypted': encrypted,
                'tr_id': tr_id,
                'len_data': len_data,
                'data': data
            }
            # print('문자열에서 딕셔너리로 변환된 데이터', extracted_data)

            if extracted_data['encrypted'] == '1':        # 암호화된 데이터인 경우
                extracted_data['data'] = self.__aes_cbc_base64_dec(data)  # 데이터 복호화

            # if (extracted_data['tr_id'] == 'H0STCNI0') or (extracted_data['tr_id'] == 'H0STCNI9'):  # 실시간 체결통보
            if extracted_data['tr_id'] in ['H0STCNI0', 'H0STCNI9']:  # 실시간 체결통보
                # print('추적2')
                # print('문자열이 실시간 체결통보')
                data_keys = self.__trans_menulist.split('|')
                # print('data_keys', data_keys)
                # print('key 개수: ', len(data_keys))
                data_values = extracted_data['data'].split('^')
                # print('data_values', data_values)
                # print('value 개수: ', len(data_values))
                data = dict(zip(data_keys, data_values))  # zip으로 묶어서 딕셔너리 형태로 변환
                data['tr_id'] = extracted_data['tr_id']   # data 에 tr_id 값 추가; 데이터 종류 구분하기 위해
                df = pd.DataFrame([data])
                # print('추적3', df)
                return df  # 완성된 현재가 데이터 df 로 리턴


            elif extracted_data['tr_id'] == 'H0STCNT0':    # 실시간 현재가  H0STCNT0
                # print('추적5')
                # print('문자열이 실시간 현재가', extracted_data['data'])
                data_keys = self.__price_menulist.split('|')
                data_values = data.split('^')
                data = dict(zip(data_keys, data_values))  # zip으로 묶어서 딕셔너리 형태로 변환
                data['tr_id'] = extracted_data['tr_id']   # data 에 tr_id 값 추가; 데이터 종류 구분하기 위해
                df = pd.DataFrame([data])
                # print('추적10', df)
                return df   # 완성된 현재가 데이터 df 로 리턴

        except:                                                   # 딕셔너리 형태의 문자열인 경우
            data = json.loads(row_data)
            # print('추적6')
            tr_id = data['header']['tr_id']
            if tr_id != 'PINGPONG': # PINGPONG 데이터가 아닌 경우
                # print('추적7')
                rt_cd = data['body']['rt_cd']

                if rt_cd == '0':                                  # 정상 데이터인 경우
                    # print('추적8')
                    self.__iv = data["body"]["output"]["iv"]      # iv 값 할당
                    self.__key = data["body"]["output"]["key"]    # key 값 할당
                    msg = data["body"]["msg1"]
                    msg_cd = data["body"]["msg_cd"]
                    return data  # 정상 데이터 리턴
                else:
                    # print('추적9')
                    return data  # 비정상 데이터 리턴

            else:
                # print('추적10')
                return data   # PINGPONG 데이터 그대로 리턴



    async def buy_update(self, ws, jango_df, trans_df):
        print('buy_update() 실행')
        ord_num = trans_df['주문번호'].values[0]

        # 주문번호가 이미 존재하는지 확인
        if ord_num in jango_df['주문번호'].values:
            print('주문번호가 있는 경우')
            # 기존 행 가져오기
            idx = jango_df[jango_df['주문번호'] == ord_num].index[0] # 기존 주문번호가 있는 행번호 가져오기

            # 수량 누적 (int로 변환 주의)
            기존_수량 = int(jango_df.at[idx, '체결수량'])
            print('기존수량: ', 기존_수량)
            신규_수량 = int(trans_df['체결수량'].values[0])
            print('신규_수량: ', 신규_수량)
            jango_df.at[idx, '체결수량'] = str(기존_수량 + 신규_수량)

            # 체결단가는 최신값으로 갱신
            기존_체결단가 = int(jango_df.at[idx, '체결단가'])
            print('기존_체결단가: ', 기존_체결단가)
            신규_체결단가 = int(trans_df['체결단가'].values[0])
            print('신규_체결단가: ', 신규_체결단가)
            평균_체결단가 = (기존_수량 * 기존_체결단가 + 신규_수량 * 신규_체결단가) / (기존_수량 + 신규_수량)
            평균_체결단가 = round(평균_체결단가)
            print('평균_체결단가')
            print(평균_체결단가)


            # jango_df.at[idx, '체결단가'] = trans_df['체결단가'].values[0]
            jango_df.at[idx, '체결단가'] = 평균_체결단가

            yymmdd = datetime.now().strftime("%y%m%d")
            체결시간 = yymmdd + trans_df['체결시간'].values[0]
            # jango_df.at[idx, '체결시간'] = trans_df['체결시간'].values[0]
            jango_df.at[idx, '체결시간'] = 체결시간
            print('buy_update() 기존 주문이 있는 경우 실행 완료')
            return jango_df

        else:  # 새로운 주문번호라면, 새로운 행에 추가
            print('주문번호가 없는 경우')
            tr_id = 'H0STCNT0'
            tran_code = trans_df['종목코드'].values[0]
            code_list = jango_df['종목코드'].unique().tolist()
            print('tran_code', tran_code)
            print('code_list', code_list)
            if tran_code not in code_list:  # 새로운 종목 구독 추가
                print('새로운 종목코드 구독 추가')
                await self.subscribe(ws=ws, tr_id=tr_id, code_list=[tran_code])
            jango_df = pd.concat([jango_df, trans_df], ignore_index=True)
            print('buy_update() 주문이 없는 경우 실행 완료')
            return jango_df


    def sell_update(self, jango_df, trans_df):
        print('sell_update() 실행')
        print(trans_df)
        ord_num = trans_df['주문번호'].values[0]

        # 주문번호가 이미 존재하는지 확인
        if ord_num in jango_df['주문번호'].values:

            idx = jango_df[jango_df['주문번호'] == ord_num].index[0] # 기존 주문번호가 있는 행번호 가져오기

            # 수량 차감 (int로 변환 주의)
            기존_수량 = int(jango_df.at[idx, '체결수량'])
            매도_수량 = int(trans_df['체결수량'])
            # 새로운_수량 = max(0, 기존_수량 - 매도_수량)  # 음수 방지
            새로운_수량 = (기존_수량 - 매도_수량)  # 음수 방지

            jango_df.at[idx, '체결수량'] = str(새로운_수량)
            jango_df.at[idx, '체결단가'] = trans_df['체결단가']
            jango_df.at[idx, '체결시간'] = trans_df['체결시간']

            if 새로운_수량 == 0:         # 수량이 모두 없어지면 행 제거
                jango_df.drop(index=idx, inplace=True)
                # kis_db.delete_data(주문번호)
                return jango_df

            else:
                # # 수량이 0이 아닐 때만 DB 업데이트
                # kis_db.update_data(주문번호, {
                #     '체결수량': str(새로운_수량),
                #     '체결단가': data['체결단가'],
                #     '체결시간': data['체결시간']
                # })
                return jango_df

        else:
            print(f"주문번호 {ord_num} 가 없는 매도가 체결되었습니다. 체결 데이터 확인 필요!!")



    # AES256 DECODE
    def __aes_cbc_base64_dec(self, cipher_text):
        cipher = AES.new(self.__key.encode('utf-8'), AES.MODE_CBC, self.__iv.encode('utf-8'))
        data = unpad(cipher.decrypt(b64decode(cipher_text)), AES.block_size).decode('utf-8')
        return data














    # ============================================================= #
    # ================== 구독 등록하는 부분 ========================== #
    # ============================================================= #

    async def subscribe(self, ws, tr_id=settings.tr_id_transaction, tr_type='1', code_list=None):
        if tr_id in ['H0STCNI0', 'H0STCNI9']:                                               # 실시간 체결알람 tr_id
            senddata = self.__req_data(tr_id=tr_id, tr_key=self.__HTS_ID, tr_type=tr_type)  # ws 에 전송할 데이터 포맷
            await ws.send(json.dumps(senddata))                                             # 실시간 체결알람 한투api에 구독 등록 요청
            print('실시간 체결알람 등록 데이터 전송', senddata)

        if tr_id == 'H0STCNT0':                                                              # 실시간 현재가 tr_id
            for tr_key in code_list:                                                         # 종목코드 순차적으로 ws 에 데이터 전송
                senddata = self.__req_data(tr_id=tr_id, tr_key=tr_key, tr_type=tr_type)
                await ws.send(json.dumps(senddata))                                          # 실시간 현재가 한투api에 구독 등록 요청
                print('실시간 현재가 등록 데이터 전송', senddata)
        print('kis_api.subscribe 함수 실행됨')

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

    # 상수 정의
    API_URL = "/uapi/domestic-stock/v1/trading/order-cash"

    def order_cash(
            self,
            env_dv: str,  # 실전모의구분 (real:실전, demo:모의)
            ord_dv: str,  # 매도매수구분 (buy:매수, sell:매도)
            cano: str,  # 종합계좌번호
            acnt_prdt_cd: str,  # 계좌상품코드
            pdno: str,  # 상품번호 (종목코드)
            ord_dvsn: str,  # 주문구분
            ord_qty: str,  # 주문수량
            ord_unpr: str,  # 주문단가
            excg_id_dvsn_cd: str,  # 거래소ID구분코드
            sll_type: str = "",  # 매도유형 (매도주문 시)
            cndt_pric: str = ""  # 조건가격
    ) -> pd.DataFrame:
        pass





















kis = kis_api()

if __name__ == '__main__':
    import asyncio
    data = '0|H0STCNT0|003|005930^094751^71950^2^1350^1.91^71690.50^71000^72300^70600^72000^71900^1^8305216^595403999350^21115^28170^7055^136.06^3060313^4163762^5^0.51^29.46^090014^2^950^090708^5^-350^090030^2^1350^20250730^20^N^93994^113056^1668973^822214^0.14^10584139^78.47^0^^71000^005930^094751^71900^2^1300^1.84^71690.50^71000^72300^70600^72000^71900^2^8305218^595404143150^21116^28170^7054^136.06^3060315^4163762^5^0.51^29.46^090014^2^900^090708^5^-400^090030^2^1300^20250730^20^N^93985^112986^1668973^822144^0.14^10584139^78.47^0^^71000^005930^094751^72000^2^1400^1.98^71690.50^71000^72300^70600^72000^71900^75^8305293^595409543150^21116^28171^7055^136.06^3060315^4163837^1^0.51^29.46^090014^2^1000^090708^5^-300^090030^2^1400^20250730^20^N^93985^112986^1668973^822144^0.14^10584139^78.47^0^^71000'
    kis = kis_api()
    asyncio.run(kis.make_data(data))