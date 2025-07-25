import uvicorn
from app.core.config import settings
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from app.websocket.realtime_websocket import endpoint
from pathlib import Path
from app.kis_invesment.account_balance import get_balance
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.PROJECT_VERSION,
    docs_url="/docs" if settings.DEBUG else None,            # DEBUG=False면 None
    redoc_url="/redoc" if settings.DEBUG else None,          # DEBUG=False면 None
    openapi_url="/openapi.json" if settings.DEBUG else None  # DEBUG=False면 None
)

# templates 경로 설정
PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "app/templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/jango")
async def jango(request: Request):
    template_data = get_balance(request)
    return templates.TemplateResponse("balance_table.html", template_data)

@app.get("/current_price")
async def current_price(request: Request):
    return templates.TemplateResponse("current_price.html", {"request": request})

@app.get("/transaction")
async def transaction(request: Request):
    return templates.TemplateResponse("transaction.html", {"request": request})

# fastapi 엔드포인트 등록
app.websocket("/ws/transaction")(endpoint)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


# uvicorn app.main:app --reload > log.txt 2>&1  # 로그 파일 남길때 커맨드창에서 실행