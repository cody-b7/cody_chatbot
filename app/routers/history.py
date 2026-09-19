"""기록 화면 라우트.

B가 소유한 pages.py 와 분리해 둔다. B는 로그인·채팅 화면을 크게 바꿀 예정이라,
같은 파일을 동시에 건드리면 충돌이 난다.

비로그인 접근은 401 대신 /login 으로 보낸다. 화면 요청에 JSON 오류를
돌려주면 사용자에게 보여줄 것이 없기 때문이다.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session as DbSession

from app.db import get_db
from app.deps import get_current_user
from app.models import User

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


def _current_user_or_none(request: Request, db: DbSession) -> User | None:
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


@router.get("/history")
def history_page(request: Request, db: DbSession = Depends(get_db)):
    """내 연습 기록. 데이터는 /api/me/* 를 호출해 채운다."""
    user = _current_user_or_none(request, db)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse(request, "history.html", {"username": user.username})
