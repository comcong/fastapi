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
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print("백그라운드 task 에러:", e)

        print("앱 종료전 kis_receiver.jango_df")
        print(kis_receiver.jango_df)
        kis_db.delete_data()
        print('kis_receiver.jango_df.columns: ', kis_receiver.jango_df.columns)
        kis_db.insert_data(kis_receiver.jango_df.to_dict(orient="records"))

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def transaction(request: Request):
    balance = kis_receiver.update_balance()
    print('balance', balance)
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