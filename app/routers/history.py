"""기록 화면 라우트.

B가 소유한 pages.py 와 분리해 둔다. B는 로그인·채팅 화면을 크게 바꿀 예정이라,
같은 파일을 동시에 건드리면 충돌이 난다.

인증은 get_current_user 의존성을 그대로 쓴다. 직접 호출하면 FastAPI 의
의존성 오버라이드가 통하지 않아, B가 인증을 교체해도 이 화면만 따로 놀게 된다.
비로그인 시 /login 으로 보내는 처리는 main.py 의 401 핸들러가 담당한다.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app.deps import get_current_user
from app.models import User

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/history")
def history_page(request: Request, user: User = Depends(get_current_user)):
    """내 연습 기록. 데이터는 /api/me/* 를 호출해 채운다."""
    return templates.TemplateResponse(
        request, "history.html", {"username": user.username}
    )
