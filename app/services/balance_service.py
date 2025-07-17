import requests
from app.services.access_token import get_access_token
import json
import time
from datetime import datetime, timedelta
# import pytz
from app.core.config import settings
from app.db.supabase import supabase
from threading import Lock
from app.services.auth_service import parse_expiration_date


def get_domestic_balance():
    """국내주식 잔고 조회"""
    # 토큰 가져오기
    access_token = get_access_token()
    print('토큰:', access_token)

    url = f"{settings.kis_base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
    print('url', url)

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {access_token}",
        "appkey": settings.KIS_APPKEY,
        "appsecret": settings.KIS_APPSECRET,
        "tr_id": settings.TR_ID,  # 국내주식 잔고 조회 TR ID
        # "custtype": "P"
    }
    print('headers', headers)

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
    print('params', params)

    max_retries = 2
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params)
            result = response.json()
            print('result', result)

            # API 응답에 오류가 있고, 재시도 가능한 경우
            if 'rt_cd' in result and result['rt_cd'] != '0' and attempt < max_retries - 1:
                print(f"API 오류: {result['msg_cd']} - {result.get('msg1', '알 수 없는 오류')}. 토큰 갱신 후 재시도...")
                # 토큰 강제 갱신 후 재시도
                access_token = get_access_token()
                headers["authorization"] = f"Bearer {access_token}"
                time.sleep(1)  # 재시도 전 1초 대기
                continue

            # 데이터 처리 함수 호출
            return process_balance_data(result)

        except Exception as e:
            print(f"잔고 조회 중 오류 발생 (시도 {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1)  # 재시도 전 1초 대기
            else:
                raise


def process_balance_data(raw_data):
    """잔고 데이터 처리 및 필터링"""

    # output1 한국어 헤더 매핑 (전체)
    output1_headers_ko = {
        'pdno': '상품번호',
        'prdt_name': '상품명',
        'trad_dvsn_name': '매매구분명',
        'bfdy_buy_qty': '전일매수수량',
        'bfdy_sll_qty': '전일매도수량',
        'thdt_buyqty': '금일매수수량',
        'thdt_sll_qty': '금일매도수량',
        'hldg_qty': '보유수량',
        'ord_psbl_qty': '주문가능수량',
        'pchs_avg_pric': '매입평균가격',
        'pchs_amt': '매입금액',
        'prpr': '현재가',
        'evlu_amt': '평가금액',
        'evlu_pfls_amt': '평가손익금액',
        'evlu_pfls_rt': '평가손익율',
        'evlu_erng_rt': '평가수익율',
        'loan_dt': '대출일자',
        'loan_amt': '대출금액',
        'stln_slng_chgs': '대주매매수수료',
        'expd_dt': '만료일자',
        'fltt_rt': '등락율',
        'bfdy_cprs_icdc': '전일대비증감',
        'item_mgna_rt_name': '종목증거금율명',
        'grta_rt_name': '보증금율명',
        'sbst_pric': '대용가격',
        'stck_loan_unpr': '주식대출단가',
        'cano': '종합계좌번호',
        'acnt_prdt_cd': '계좌상품코드'
    }

    # output2 한국어 헤더 매핑 (전체)
    output2_headers_ko = {
        'dnca_tot_amt': '예수금총금액',
        'nxdy_excc_amt': '익일정산금액',
        'prvs_rcdl_excc_amt': '가수도정산금액',
        'cma_evlu_amt': 'CMA평가금액',
        'bfdy_buy_amt': '전일매수금액',
        'thdt_buy_amt': '금일매수금액',
        'nxdy_auto_rdpt_amt': '익일자동상환금액',
        'bfdy_sll_amt': '전일매도금액',
        'thdt_sll_amt': '금일매도금액',
        'd2_auto_rdpt_amt': 'D+2자동상환금액',
        'bfdy_tlex_amt': '전일제비용금액',
        'thdt_tlex_amt': '금일제비용금액',
        'tot_loan_amt': '총대출금액',
        'scts_evlu_amt': '유가증권평가금액',
        'tot_evlu_amt': '총평가금액',
        'nass_amt': '순자산금액',
        'fncg_gld_auto_rdpt_yn': '융자금자동상환여부',
        'pchs_amt_smtl_amt': '매입금액합계금액',
        'evlu_amt_smtl_amt': '평가금액합계금액',
        'evlu_pfls_smtl_amt': '평가손익합계금액',
        'all_rcmd_code': '전체추천코드',
        'bfdy_fncg_sttl_amt': '전일융자결제금액',
        'bfdy_gld_sttl_amt': '전일대출결제금액',
        'cma_evlu_amt_icdc': 'CMA평가금액증감',
        'bfdy_tot_asst_evlu_amt': '전일총자산평가금액',
        'asst_icdc_amt': '자산증감액',
        'asst_icdc_erng_rt': '자산증감수익율',
        'cano': '종합계좌번호',
        'acnt_prdt_cd': '계좌상품코드'
    }

    # 제외할 컬럼들을 한글로 정의
    output1_exclude_columns_ko = [
        '종합계좌번호',
        '계좌상품코드',
        '대출일자',
        '대출금액',
        '대주매매수수료',
        '만료일자',
        '등락율'
    ]

    output2_exclude_columns_ko = [
        '종합계좌번호',
        '계좌상품코드',
        '융자금자동상환여부',
        '전체추천코드'
    ]

    # 한글 컬럼명을 영문 컬럼명으로 변환
    def get_english_columns_to_exclude(korean_columns, headers_ko_mapping):
        english_columns = []
        for kor_col in korean_columns:
            for eng_col, ko_col in headers_ko_mapping.items():
                if ko_col == kor_col:
                    english_columns.append(eng_col)
                    break
        return english_columns

    output1_exclude_columns = get_english_columns_to_exclude(output1_exclude_columns_ko, output1_headers_ko)
    output2_exclude_columns = get_english_columns_to_exclude(output2_exclude_columns_ko, output2_headers_ko)

    # 원본 데이터 추출
    output1_data = raw_data.get('output1', [])
    output2_data = raw_data.get('output2', [])

    # 헤더 필터링
    if output1_data:
        all_output1_columns = list(output1_data[0].keys())
        output1_headers = [col for col in all_output1_columns if col not in output1_exclude_columns]
    else:
        output1_headers = []

    if output2_data:
        all_output2_columns = list(output2_data[0].keys())
        output2_headers = [col for col in all_output2_columns if col not in output2_exclude_columns]
    else:
        output2_headers = []

    # 최종 결과 반환
    return {
        'output1': output1_data,
        'output1_headers': output1_headers,
        'output1_headers_ko': output1_headers_ko,
        'output2': output2_data,
        'output2_headers': output2_headers,
        'output2_headers_ko': output2_headers_ko
    }


