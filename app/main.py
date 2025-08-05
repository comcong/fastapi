from contextlib import asynccontextmanager
from pathlib import Path
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, Request, WebSocket
import asyncio
import uvicorn

import kis_receiver
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
    kis_db.delete_data()
    kis_db.insert_data(kis_receiver.jango_df.to_dict(orient="records"))

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def transaction(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket_manager.manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # 클라이언트 메시지를 무시
    except:
        websocket_manager.manager.disconnect(websocket)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
