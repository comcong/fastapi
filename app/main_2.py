import uvicorn
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, Request, WebSocket
from websocket_manager import manager
import kis_receiver
import asyncio

# templates 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "app/templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))



@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시
    print('앱 실행전')
    task = asyncio.create_task(kis_receiver.start_kis_receiver())  # 백그라운드에서 start_kis_receiver() 실행
    yield
    # 서버 종료 시 (필요하면 정리 작업)
    print('앱 종료전')
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def transaction(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # 클라이언트 메시지를 무시
    except:
        manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
