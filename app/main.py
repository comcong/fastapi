from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.templating import Jinja2Templates
from app.websocket.realtime_websocket import websocket_endpoint
from pathlib import Path
from app.services.account_balance import get_domestic_balance
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
    template_data = get_domestic_balance(request)
    return templates.TemplateResponse("balance_table.html", template_data)

# WebSocket 엔드포인트 등록
app.websocket("/ws")(websocket_endpoint)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)