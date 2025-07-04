from fastapi import FastAPI
from controller import items, users, admins
app = FastAPI()

app.include_router(items.router)
app.include_router(users.router)
app.include_router(admins.router)
@app.get("/")
def read_root():
    return {"Hello": "World"}




