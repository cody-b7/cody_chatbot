"""화면 라우트."""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.scenarios import SCENARIOS

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
def index(request: Request):
    if not request.session.get("user_id"):
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(
        request,
        "index.html",
        {"scenarios": SCENARIOS},
    )


@router.get("/login")
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)

    error = request.query_params.get("error")

    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": error},
    )


@router.get("/signup")
def signup_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)

    error = request.query_params.get("error")

    return templates.TemplateResponse(
        request,
        "signup.html",
        {"error": error},
    )