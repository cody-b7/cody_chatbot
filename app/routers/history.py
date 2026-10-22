"""기록 화면 라우트.

인증은 get_current_user 의존성을 그대로 쓴다. 직접 호출하면 FastAPI 의
의존성 오버라이드가 통하지 않아, 인증 구현이 바뀌어도 이 화면만 따로 놀게 된다.
비로그인 시 /login 으로 보내는 처리는 main.py 의 401 핸들러가 담당한다.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates

from app.deps import get_current_user
from app.models import User
from app.scenarios import SCENARIOS

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")

# API 는 상황을 영어 키(cafe)로 돌려준다. 화면에는 한국어 이름(카페)을 보여준다.
SCENARIO_LABELS = {s.key: s.label for s in SCENARIOS}


def _context(user: User) -> dict:
    return {"username": user.username, "labels": SCENARIO_LABELS}


@router.get("/history")
def history_page(request: Request, user: User = Depends(get_current_user)):
    """내 연습 기록. 데이터는 /api/me/* 를 호출해 채운다."""
    return templates.TemplateResponse(request, "history.html", _context(user))


@router.get("/corrections")
def corrections_page(request: Request, user: User = Depends(get_current_user)):
    """자주 틀리는 표현. 쌓인 교정을 복습용으로 되돌려 준다."""
    return templates.TemplateResponse(request, "corrections.html", _context(user))
