import requests
from app.core.config import settings
from app.services.kis_auth import get_access_token

# 국내주식 잔고 조회
def get_balance(request=None):
    print('====================================')
    print('get_balance 실행')
    print('====================================')
    if settings.KIS_USE_MOCK == True:
        base_url = "https://openapivts.koreainvestment.com:29443"
        tr_id = 'VTTC8434R'
    elif settings.KIS_USE_MOCK == False:
        base_url = "https://apivts.koreainvestment.com:9443"
        tr_id = 'TTTC8434R'
    # 토큰 가져오기
    access_token = get_access_token()

    url = f"{base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": settings.KIS_APPKEY,
        "appsecret": settings.KIS_APPSECRET,
        "tr_id": tr_id
    }

    params = {
        "CANO": settings.KIS_CANO,
        "ACNT_PRDT_CD": settings.KIS_ACNT_PRDT_CD,
        "AFHR_FLPR_YN": "N",
        "OFL_YN": "",
        "INQR_DVSN": "02",
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N",
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": "00",
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": ""
    }

    response = requests.get(url, headers=headers, params=params)
    result = response.json()
    print('account_balance.py_get_balance() 에러: ', result)
    if 'output2' in result:
        d2_cash = result['output2'][0]['prvs_rcdl_excc_amt']
        return d2_cash
    else:
        return None

if __name__ == '__main__':
    res = get_balance()
    예수금0 = res['output2'][0]['dnca_tot_amt']
    예수금1 = res['output2'][0]['nxdy_excc_amt']
    예수금2 = res['output2'][0]['prvs_rcdl_excc_amt']
    유가증권평가금액합계 = res['output2'][0]['scts_evlu_amt']
    총평가금액 = res['output2'][0]['tot_evlu_amt']         # 유가증권 평가금액 합계금액 + D+2 예수금
    유가증권매입금액  = res['output2'][0]['pchs_amt_smtl_amt']

    계산 = int(예수금2) + int(유가증권평가금액합계)
    잔고 = int(예수금2) + int(유가증권매입금액)


    print('예수금0', 예수금0)
    print('예수금1', 예수금1)
    print('예수금2', 예수금2)
    print('유가증권 매입금액', 유가증권매입금액)
    print('유가증권 평가금액합계', 유가증권평가금액합계)
    print()
    print()


    print('잔고', 잔고)
    print('예수금2 + 평가금액', 계산)
    print('총평가금액', 총평가금액)

    # 잔고  =  예수금2 + 매입금액 합계
    # 평가금 = 예수금2 + 평가금액 합계
    # 매수가능금액 = 예수금2 - 매입금액 합계

