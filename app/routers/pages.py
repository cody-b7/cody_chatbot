"""화면 라우트 (서버 렌더링).

화면 뼈대는 서버가 Jinja2 로 그리고, 바뀌는 데이터는 화면 JS 가 /api/* 를 불러 채운다.

로그인이 필요한 화면은 모두 get_current_user 의존성으로 막는다.
화면마다 세션 값을 직접 확인하면, 계정이 지워진 쿠키처럼 "세션은 있는데
사용자는 없는" 경우를 화면마다 다르게 처리하게 된다. 비로그인 시 /login 으로
보내는 처리는 main.py 의 401 핸들러가 담당한다.

API 문서(Swagger)에는 나오지 않게 한다 — HTML 을 돌려주는 화면이라서.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.deps import get_current_user
from app.models import User
from app.scenarios import SCENARIOS
from app.security import PASSWORD_MIN_LENGTH
from app.templating import templates

router = APIRouter(tags=["pages"], include_in_schema=False)

# API 는 상황을 영어 키(cafe)로 돌려준다. 화면에는 한국어 이름(카페)을 보여준다.
SCENARIO_LABELS = {s.key: s.label for s in SCENARIOS}


def _context(user: User) -> dict:
    return {"username": user.username, "labels": SCENARIO_LABELS}


@router.get("/")
def practice_page(request: Request, user: User = Depends(get_current_user)):
    """연습 화면."""
    return templates.TemplateResponse(
        request, "index.html", {"username": user.username, "scenarios": SCENARIOS}
    )


@router.get("/history")
def history_page(request: Request, user: User = Depends(get_current_user)):
    """내 연습 기록. 데이터는 /api/me/* 를 호출해 채운다."""
    return templates.TemplateResponse(request, "history.html", _context(user))


@router.get("/corrections")
def corrections_page(request: Request, user: User = Depends(get_current_user)):
    """자주 틀리는 표현. 쌓인 교정을 복습용으로 되돌려 준다."""
    return templates.TemplateResponse(request, "corrections.html", _context(user))


@router.get("/login")
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {})


@router.get("/signup")
def signup_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request, "signup.html", {"password_min_length": PASSWORD_MIN_LENGTH}
    )
