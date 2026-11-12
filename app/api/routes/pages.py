"""화면 (서버 렌더링). 뼈대는 Jinja2 로 그리고, 데이터는 화면 JS 가 /api 를 불러 채운다."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.api.deps import get_current_user
from app.api.templating import templates
from app.core.scenarios import LABELS, SCENARIOS
from app.core.security import PASSWORD_MIN_LENGTH
from app.db.models import User

router = APIRouter(include_in_schema=False)  # HTML 이라 API 문서에서 뺀다


@router.get("/")
def practice_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        request, "index.html", {"username": user.username, "scenarios": SCENARIOS}
    )


@router.get("/history")
def history_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        request, "history.html", {"username": user.username, "labels": LABELS}
    )


@router.get("/corrections")
def corrections_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        request, "corrections.html", {"username": user.username, "labels": LABELS}
    )


@router.get("/login")
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html")


@router.get("/signup")
def signup_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request, "signup.html", {"password_min_length": PASSWORD_MIN_LENGTH}
    )
