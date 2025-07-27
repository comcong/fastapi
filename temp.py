from app.kis_invesment.kis_manager import kis_api, subscribe_code, unsubscribe_code
from app.db.kis_db import get_current_code_list  # 예: DB에서 종목코드 가져오는 함수
# 위 함수들은 외부에서 구현되어 있다고 가정

...

async def combined_kis_task():
    tr_id_price = 'H0STCNT0'
    tr_id_transaction = 'H0STCNI9'

    kis = kis_api()
    prev_code_set = set(code_list)  # 최초 구독 코드
    first_run = True                # 최초 1회는 기존 코드 사용

    async with websockets.connect(kis.url) as ws:
        print("KIS 웹소켓에 연결됨")

        # 최초 구독 요청
        await kis.subscribe(ws=ws, tr_id=tr_id_transaction)
        await kis.subscribe(ws=ws, tr_id=tr_id_price, code_list=code_list)

        price_df = None
        trans_df = None

        while True:
            try:
                # 📌 1. 주기적으로 종목코드 목록을 확인
                if not first_run:
                    current_code_set = set(get_current_code_list())  # 예: DB에서 현재 보유 종목코드 조회

                    # 📌 2. 추가된 코드 구독 등록
                    new_codes = current_code_set - prev_code_set
                    for code in new_codes:
                        await subscribe_code(ws=ws, tr_id=tr_id_price, code=code)

                    # 📌 3. 제거된 코드 구독 해제
                    removed_codes = prev_code_set - current_code_set
                    for code in removed_codes:
                        await unsubscribe_code(ws=ws, tr_id=tr_id_price, code=code)

                    # 현재 코드셋을 다음 루프 기준으로 저장
                    prev_code_set = current_code_set

                first_run = False

                # 📡 실시간 데이터 수신
                raw_data = await asyncio.wait_for(ws.recv(), timeout=2.0)
                print("수신된 원본 데이터: ", raw_data)
                data = await kis.make_data(raw_data)
                print("수신된 가공 데이터: ", data)

                if isinstance(data, pd.DataFrame):
                    tr_id = data.iloc[0]['tr_id']
                    if tr_id == 'H0STCNT0':
                        price_df = data.copy()
                    elif tr_id in ['H0STCNI9', 'H0STCNI0']:
                        trans_df = data.copy()

                    if price_df is not None and trans_df is not None:
                        df = trans_df.merge(
                            price_df[['종목코드', '현재가']], on='종목코드', how='left'
                        )
                        json_data = df.to_dict(orient="records")
                        await broadcast(json.dumps({
                            "type": "stock_data",
                            "data": json_data
                        }, ensure_ascii=False))

                else:
                    await broadcast(json.dumps({
                        "type": "message",
                        "data": data
                    }, ensure_ascii=False))

            except asyncio.TimeoutError:
                # 매 루프마다 코드 목록 업데이트를 위한 타임아웃
                continue
            except Exception as e:
                print("웹소켓 수신 오류:", e)
                await asyncio.sleep(5)
                continue
