"""회원가입 / 로그인 / 로그아웃.

폼(POST) 기반이다. 상태코드 약속:
- POST /signup
  - 성공: 303 → /            (새로고침해도 폼이 다시 전송되지 않게 PRG 패턴)
  - 형식 오류: 422 + 가입 화면 (invalid_username, password_*)
  - 중복·예약 아이디: 409 + 가입 화면 (duplicate, reserved_username)
- POST /login
  - 성공: 303 → /
  - 실패: 401 + 로그인 화면 (bad_credentials)
- POST /logout
  - 303 → /login

실패는 리다이렉트하지 않고 화면을 바로 그린다. 리다이렉트(303)로 돌려보내면
실패한 요청이 상태코드로는 성공 흐름과 구분되지 않는다.

계정 규칙(아이디 정규화, 비밀번호 정책)은 app/security.py 에 있다.
"""

import logging

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.db import get_db
from app.log_events import Event
from app.models import User
from app.security import (
    PASSWORD_MIN_LENGTH,
    check_password,
    check_username,
    hash_password,
    normalize_username,
    verify_password,
)
from app.templating import templates

logger = logging.getLogger("cody.auth")
router = APIRouter(tags=["auth"])


def _find_user(db: DbSession, username: str) -> User | None:
    """정규화한 아이디로 사용자를 찾는다.

    정규화 도입 전에 "Tester" 처럼 대문자로 가입한 계정도 함께 찾기 위해 lower() 로 비교한다.
    """
    return db.query(User).filter(func.lower(User.username) == username).first()


def _signup_error(request: Request, code: str, username: str, status_code: int):
    logger.info("%s reason=%s", Event.SIGNUP_FAILED, code)
    return templates.TemplateResponse(
        request,
        "signup.html",
        {"error": code, "entered_username": username, "password_min_length": PASSWORD_MIN_LENGTH},
        status_code=status_code,
    )


@router.post("/signup", summary="회원가입 (폼)")
def signup(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    db: DbSession = Depends(get_db),
):
    username = normalize_username(username)

    username_error = check_username(username)
    if username_error == "reserved_username":
        return _signup_error(request, username_error, username, status.HTTP_409_CONFLICT)
    if username_error:
        return _signup_error(
            request, username_error, username, 422
        )

    password_error = check_password(password, username)
    if password_error:
        return _signup_error(
            request, password_error, username, 422
        )

    if _find_user(db, username) is not None:
        return _signup_error(request, "duplicate", username, status.HTTP_409_CONFLICT)

    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        # 위에서 확인한 사이에 같은 아이디가 먼저 가입된 경우 (DB unique 제약이 최종 방어선)
        db.rollback()
        return _signup_error(request, "duplicate", username, status.HTTP_409_CONFLICT)

    request.session["user_id"] = user.id
    logger.info("%s user_id=%s", Event.SIGNUP_SUCCESS, user.id)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/login", summary="로그인 (폼)")
def login(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    db: DbSession = Depends(get_db),
):
    username = normalize_username(username)
    user = _find_user(db, username) if username else None

    # 없는 아이디와 틀린 비밀번호를 같은 응답으로 돌려준다.
    # 다르게 답하면 어떤 아이디가 가입돼 있는지 알아낼 수 있다.
    if user is None or not verify_password(password, user.password_hash):
        logger.info("%s user_exists=%s", Event.LOGIN_FAILED, user is not None)
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "bad_credentials", "entered_username": username},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # 로그인 전 세션을 비우고 새로 담는다 (이전 사용자의 세션 값이 섞이지 않게)
    request.session.clear()
    request.session["user_id"] = user.id
    logger.info("%s user_id=%s", Event.LOGIN_SUCCESS, user.id)
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout", summary="로그아웃")
def logout(request: Request):
    user_id = request.session.get("user_id")
    request.session.clear()
    logger.info("%s user_id=%s", Event.LOGOUT, user_id)
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
