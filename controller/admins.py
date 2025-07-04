
from fastapi import APIRouter
from model import pgsql_test

router = APIRouter(
    prefix="/admins",
    tags=["admins"],
    responses={404: {"description": "Not found"}},
)

@router.get("/list")
def list_admin():
    result = pgsql_test.list_admin()
    return result