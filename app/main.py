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
    return templates.TemplateResponse("balance_table.html", {
        "request": request,
        "output1": res['output1'],
        "output1_headers": res['output1_headers'],
        "output1_headers_ko": res['output1_headers_ko'],
        "output2": res['output2'],
        "output2_headers": res['output2_headers'],
        "output2_headers_ko": res['output2_headers_ko']
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