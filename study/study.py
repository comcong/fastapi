# study.py
import uvicorn
import asyncio
from fastapi import FastAPI,  Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from pathlib import Path
import pandas as pd
import numpy as np

# templates 경로 설정
PROJECT_ROOT = Path(__file__).parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI()

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await asyncio.sleep(1)

            # 랜덤 DataFrame 생성
            df = pd.DataFrame({
                "A": np.random.randint(0, 100, 5),
                "B": np.random.randint(0, 100, 5),
                "C": np.random.randint(0, 100, 5)
            })

            html_table = df.to_html(index=False)
            tbody_content = html_table.split("<tbody>")[1].split("</tbody>")[0]
            html = f'<tbody id="table-body" hx-swap-oob="innerHTML">{tbody_content}</tbody>'
            await websocket.send_text(html)

    except Exception as e:
        print("웹소켓 연결 종료:", e)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
