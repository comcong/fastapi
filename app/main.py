from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
import json
import asyncio
import random
from pathlib import Path
from app.services.balance_service import get_domestic_balance
app = FastAPI()

# templates 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "app/templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/")
async def get(request: Request):
    return templates.TemplateResponse("jango.html", {"request": request})


@app.get("/jango")
async def jango(request: Request):
    res = get_domestic_balance()
    print(res)

    # output1(계좌잔고) 데이터 처리
    output1_data = res['output1']

    # output2(계좌평가) 데이터 처리
    output2_data = res['output2']

    # output1 한국어 헤더 매핑
    output1_headers_ko = {
        'pdno': '종목코드',
        'prdt_name': '종목명',
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

    # output2 한국어 헤더 매핑
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
        'tot_stln_slng_chgs': '총대주매각대금',
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

    # 제외할 컬럼 한글로 기입
    output1_exclude_columns_ko = [
        '대출일자',
        '대출금액',
        '대주매매수수료',
        '만료일자',
        '보증금율명',
        '대용가격',
        '주식대출단가'
    ]

    output2_exclude_columns_ko = [

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

    # 전체 컬럼에서 제외할 컬럼 빼기
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

    return templates.TemplateResponse("balance_table.html", {
        "request": request,
        "output1": output1_data,
        "output1_headers": output1_headers,
        "output1_headers_ko": output1_headers_ko,
        "output2": output2_data,
        "output2_headers": output2_headers,
        "output2_headers_ko": output2_headers_ko
    })


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            # 랜덤 데이터 생성
            data1 = random.uniform(0, 100)
            data2 = random.uniform(200, 300)

            message = {
                "temperature": data1,
                "humidity": data2
            }

            await websocket.send_text(json.dumps(message))

            # 1초 대기
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        print("클라이언트 연결 종료")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)