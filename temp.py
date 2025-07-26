async def make_data(self, data):  # ws 에서 수신되는 데이터 가공
    if (tr_id == 'H0STCNI0') or (tr_id == 'H0STCNI9'):  # 체결통보
        try:
            data = json.loads(data)
            if 'body' in data and 'output' in data['body']:
                iv = data['body']['output']['iv']
                key = data['body']['output']['key']
            else:
                pass

        except:
            cipher_text = data.split('|')[3]
            print('암호데이터: ', cipher_text)
            data = self.__aes_cbc_base64_dec(key, iv, cipher_text)
            print('해독데이터: ', data)
        return data

    elif tr_id == 'H0STCNT0':  # 실시간 체결가
        try:
            data = json.loads(data)
        except:
            data = self.__price_data_cleaning(data)
        return data

    elif tr_id == 'PINGPONG':
        data = json.loads(data)
        return data



# 구독 성공 메시지
'''
{
  "header": {
    "tr_id": "H0STCNT0",
    "tr_key": "005930",
    "encrypt": "N"
  },
  "body": {
    "rt_cd": "0",
    "msg_cd": "OPSP0000",
    "msg1": "SUBSCRIBE SUCCESS",
    "output": {
      "iv": "e2e0531bfa1122c6",
      "key": "b3cbf02d19f564a0d2cbe5b1edcd5b6d"
    }
  }
}
'''

'''
1. 정상 등록 여부 (JSON)
- JSON["body"]["msg1"] - 정상 응답 시, SUBSCRIBE SUCCESS
- JSON["body"]["output"]["iv"] - 실시간 결과 복호화에 필요한 AES256 IV (Initialize Vector)
- JSON["body"]["output"]["key"] - 실시간 결과 복호화에 필요한 AES256 Key
'''


'0|H0STCNT0|001|005930^120651^67050^5^-750^-1.11^67620.79^68100^68500^67000^67100^67000^200^8293601^560819903500^25773^26194^421^67.01^4648298^3114657^1^0.38^46.80^090008^5^-1050^090433^5^-1450^100933^2^50^20250722^20^N^122087^257541^794914^1365374^0.14^10573794^78.44^0^^68100'
# 암호화 유무 : 0:암호화 되지 않은 데이터,  1:암호화된 데이터
# TR_ID : 등록한 tr_id (ex. H0STCNT0)
# 데이터 건수 : (ex. 001 인 경우 데이터 건수 1건, 004인 경우 데이터 건수 4건)
# 응답 데이터 : 아래 response 데이터 참조 ( ^로 구분됨)

'''
※ 데이터가 많은 경우 여러 건을 페이징 처리해서 데이터를 보내는 점 참고 부탁드립니다.
ex) 0|H0STCNT0|004|... 인 경우 004가 데이터 개수를 의미하여, 뒤에 체결데이터가 4건 들어옴
→ 0|H0STCNT0|004|005930^123929...(체결데이터1)...^005930^123929...(체결데이터2)...^005930^123929...(체결데이터3)...^005930^123929...(체결데이터4)...
'''

#가공된 실시간 체결 데이터

'''
{
  "header": {
    "tr_id": "H0STCNT0",
    "tr_key": "005930"
  },
  "body": {
    "mksc_shrn_iscd": "005930",        # 종목코드 (삼성전자)
    "stck_prpr": "78200",              # 현재가
    "prdy_vrss_sign": "5",             # 전일 대비 부호 (1:상한, 2:상승, 3:보합, 4:하한, 5:하락)
    "prdy_ctrt": "-0.26",              # 전일 대비율(%)
    "acml_tr_pbmn": "92123764500",     # 누적 거래대금
    "acml_vol": "1179333",             # 누적 거래량
    "prdy_vrss": "-200",               # 전일 대비
    "askp": "78200",                   # 매도호가
    "bidp": "78100",                   # 매수호가
    "hghp": "78700",                   # 고가
    "lwp": "77500",                    # 저가
    "opnprc": "78000",                 # 시가
    "last_cntr_time": "141523",        # 체결 시간
    "vol_tnrt": "0.03",                # 거래량 회전율
    "lstn_stcn": "59697837",           # 상장 주식 수
    "cpfn": "0",                       # 자본금
    "hts_kor_isnm": "삼성전자",         # 종목명
    "mrkt_tot_amt": "461894775600000", # 시가총액
    "lstn_stcn": "59697837"            # 상장주식수
  }
}
'''



# 구독 실패
'''
{
  "header": {
    "tr_id": "H0STCNT0",
    "tr_key": "005930",
    "encrypt": "N"
  },
  "body": {
    "rt_cd": "-1",
    "msg_cd": "OPS10002",
    "msg1": "종목코드 오류",
    "output": {}
  }
}
'''

# 실시간 데이터 사용량 초과
'''
{
  "header": {
    "tr_id": "H0STCNT0",
    "tr_key": "005930",
    "encrypt": "N"
  },
  "body": {
    "rt_cd": "-1",
    "msg_cd": "OPS10004",
    "msg1": "실시간 데이터 사용량 제한을 초과하였습니다.",
    "output": {}
  }
}
'''


# appkey 중복사용 에러
'''
{
  "header": {
    "tr_id": "H0STCNT0", 
    "tr_key": "005930"
  },
  "body": {
    "rt_cd": "1",
    "msg_cd": "OPSP0003",
    "msg1": "AppKey is already in use"
  }
}
'''







