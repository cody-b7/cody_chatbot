"""화면 라우트.

로그인 여부는 세션 값이 아니라 실제 사용자로 판단한다.
세션에 user_id 가 남아 있어도 그 계정이 없을 수 있다(DB 초기화, 계정 삭제).
세션 값만 보면 채팅 화면은 뜨는데 모든 요청이 401 로 실패하고,
/login 으로 가려 해도 다시 / 로 튕겨 빠져나올 수 없었다.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session as DbSession

from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.scenarios import SCENARIOS

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


def _logged_in_user(request: Request, db: DbSession) -> User | None:
    """세션의 user_id 가 실제로 존재하는 사용자일 때만 돌려준다.

    없는 계정을 가리키는 세션은 여기서 비워서, 다음 요청부터는
    깨끗한 비로그인 상태로 다룬다.
    """
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    user = db.get(User, user_id)
    if user is None:
        request.session.clear()
    return user


@router.get("/")
def index(request: Request, user: User = Depends(get_current_user)):
    # 비로그인이면 get_current_user 가 401 을 내고,
    # main.py 의 핸들러가 브라우저 요청을 /login 으로 보낸다.
    return templates.TemplateResponse(
        request,
        "index.html",
        {"scenarios": SCENARIOS, "username": user.username},
    )


def _auth_page(request: Request, db: DbSession, template: str):
    if _logged_in_user(request, db) is not None:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request, template, {"error": request.query_params.get("error")}
    )


@router.get("/login")
def login_page(request: Request, db: DbSession = Depends(get_db)):
    return _auth_page(request, db, "login.html")


@router.get("/signup")
def signup_page(request: Request, db: DbSession = Depends(get_db)):
    return _auth_page(request, db, "signup.html")
