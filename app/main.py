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
async def lifespan(app: FastAPI):
    task = asyncio.create_task(kis_receiver.start_kis_receiver())  # 백그라운드에서 start_kis_receiver() 실행
    try:

        yield

    finally:
        print("앱 종료 전 cleanup 시작")

        # 1. 안전하게 jango_df 복사
        safe_df = None
        try:
            if getattr(kis_receiver, "jango_df", None) is not None:
                safe_df = kis_receiver.jango_df.copy()
                print("jango_df 복사 성공, shape:", safe_df.shape)
            else:
                print("jango_df 없음(None 상태)")
        except Exception as e:
            print("jango_df 복사 실패:", e)

        # 2. task 종료 처리
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print("백그라운드 task 에러:", e)

        # 3. DB 정리 (delete → insert)
        try:
            kis_db.delete_data()
            print("DB 데이터 삭제 완료")

            if safe_df is not None and not safe_df.empty:
                print("jango_df.columns:", safe_df.columns)
                kis_db.insert_data(safe_df.to_dict(orient="records"))
                print("DB 데이터 insert 완료")
            else:
                print("safe_df 가 없거나 비어있음 → insert 생략")
        except Exception as e:
            print("DB 처리 중 에러:", e)

        print("앱 종료 cleanup 완료")

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def transaction(request: Request):
    balance = await kis_receiver.update_balance()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "balance": balance,
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
            res = await kis.sell_stock(json_data['data'])
            if res:
                sell_order_no, sell_order_price, sell_order_qty = res
                print("매도 주문 응답 정상", sell_order_no, sell_order_price, sell_order_qty)
                kis_receiver.jango_df.loc[kis_receiver.jango_df['매수_주문번호'] == json_data['data']['order_number'], ['매도_주문번호', '매도_주문가격', '매도_주문수량']] = (sell_order_no, sell_order_price, sell_order_qty)
                json_data = kis_receiver.jango_df.drop(columns='체결량').to_dict(orient="records")
                data = {"type": "stock_data", "data": json_data}
                await websocket_manager.manager.broadcast(json.dumps(data))

    except Exception as e:
        print(["[main.py - 1 오류]"], e)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)