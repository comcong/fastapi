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
PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "app/templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))



@asynccontextmanager
async def lifespan(app: FastAPI):

    task = asyncio.create_task(kis_receiver.start_kis_receiver())  # 백그라운드에서 start_kis_receiver() 실행
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    if not kis_receiver.jango_df.empty:
        kis_db.delete_data()
        print("앱 종료전 kis_receiver.jango_df")
        print(kis_receiver.jango_df)
        kis_db.insert_data(kis_receiver.jango_df.to_dict(orient="records"))

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def transaction(request: Request):
    return templates.TemplateResponse("test.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.manager.connect(websocket)
    await kis_receiver.send_initial_data(websocket)
    try:
        while True:
            fws_data = await websocket.receive_text()
            print('fws_data')
            print(fws_data)
            # {"type":"sell_order","data":{"order_number":"3444","stock_code":"233740","stock_name":"KODEX 코스닥150레버리지","quantity":"1","current_price":"9065"}}
            json_data = json.loads(fws_data)
            await kis.sell_stock(json_data['data'])
    except:
        websocket_manager.manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
