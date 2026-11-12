"""회원가입·로그인·로그아웃 (HTML 폼).

성공하면 303 으로 이동한다 (새로고침해도 폼이 다시 전송되지 않게).
실패하면 화면을 바로 다시 그리며 상태코드로 이유를 구분한다.
  422 형식 오류 / 409 중복·예약 아이디 / 401 로그인 실패
"""

import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.templating import templates
from app.core.logging import Event
from app.core.security import PASSWORD_MIN_LENGTH
from app.db.session import get_db
from app.services import auth as auth_service

logger = logging.getLogger("cody.auth")
router = APIRouter(tags=["auth"])

_CONFLICT_ERRORS = {"duplicate", "reserved_username"}


@router.post("/signup", summary="회원가입 (폼)")
def signup(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    user, error = auth_service.register(db, username, password)
    if error:
        return templates.TemplateResponse(
            request,
            "signup.html",
            {"error": error, "entered_username": username.strip(),
             "password_min_length": PASSWORD_MIN_LENGTH},
            status_code=409 if error in _CONFLICT_ERRORS else 422,
        )
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.post("/login", summary="로그인 (폼)")
def login(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    user = auth_service.authenticate(db, username, password)
    if user is None:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "bad_credentials", "entered_username": username.strip()},
            status_code=401,
        )
    request.session.clear()  # 이전 사용자의 세션 값이 섞이지 않게
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.post("/logout", summary="로그아웃")
def logout(request: Request):
    logger.info("%s user_id=%s", Event.LOGOUT, request.session.get("user_id"))
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
