"""화면 라우트.

TODO(B): 이 파일과 app/templates/ 전체가 B의 작업 범위다.
         - 비로그인 사용자가 / 로 오면 /login 으로 보낼 것
         - 챗 화면에서 POST /api/chat 을 호출하고 reply·correction 을 표시할 것
         - 503 응답이 오면 body 의 message 를 그대로 사용자에게 보여줄 것
"""

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.schemas import SCENARIOS

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"scenarios": SCENARIOS}
    )


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})
