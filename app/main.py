# main.py
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, Request, WebSocket
import asyncio
import uvicorn
import json

import kis_receiver
from app.kis_invesment.kis_manager import kis
import websocket_manager
from app.db import kis_db

# templates 경로 설정
PROJECT_ROOT = Path(__file__).parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    task = asyncio.create_task(kis_receiver.start_kis_receiver())  # 백그라운드에서 start_kis_receiver() 실행
    try:

        yield

    finally:

        print("앱 종료 전 cleanup 시작")
        # 1. task 종료 처리
        task.cancel()
        error_in_task = False
        try:
            await task
        except asyncio.CancelledError:  # 정상적인 cancel
            pass
        except Exception as e:
            error_in_task = True
            print("백그라운드 task 에러:", e)

        # 2. 안전하게 jango_df 복사
        safe_df = None
        try:
            safe_df = kis_receiver.jango_df.copy()
            print("jango_df 복사 성공, shape:", safe_df.shape)
            print("safe_df.info(): ", '\n')
            safe_df.info()

        except Exception as e:
            print("jango_df 복사 실패:", e)


        # 3. task 가 정상 종료 + safe_df 유효할 때만 DB 저장
        if not error_in_task and safe_df is not None:
            try:
                kis_db.del_and_insert(safe_df)
                print("DB 트랜잭션 저장 완료")
            except Exception as e:
                print("DB 처리 중 에러: ", e)

        else:
            print('task 실패 또는 safe_df None → DB 저장 생략')

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def transaction(request: Request):
    data = await kis_receiver.update_balance()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "balance": data[0],
            "tot_acc_value": data[1],
            "acc_profit": data[2],
            "d2_cash": data[3]
        }
    )


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.manager.connect(websocket)
    await kis_receiver.send_initial_data(websocket)
    try:
        while True:
            fws_data = await websocket.receive_text()
            print('fws_data')
            print(fws_data)
            json_data = json.loads(fws_data)
            res = await kis.sell_order(json_data['data'])
            print('res', res)
            if 'output1' in res:
                sell_order_no, sell_order_price, sell_order_qty = res['output1']
                print("매도 주문 응답 정상", sell_order_no, sell_order_price, sell_order_qty)
                kis_receiver.jango_df.loc[kis_receiver.jango_df['매수_주문번호'] == json_data['data']['order_number'], ['매도_주문번호', '매도_주문가격', '매도_주문수량']] = (sell_order_no, sell_order_price, sell_order_qty)
                json_data = kis_receiver.jango_df.drop(columns='체결량').to_dict(orient="records")
                data = {"type": "stock_data", "data": json_data}
                await websocket_manager.manager.broadcast(json.dumps(data))

            print("json.dumps(res['output2'])", json.dumps(res['output2']))
            await websocket_manager.manager.broadcast(json.dumps(res['output2']))
    except Exception as e:
        print(["[main.py - 1 오류]"], e)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)