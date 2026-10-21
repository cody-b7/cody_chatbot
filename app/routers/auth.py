"""회원가입 / 로그인 / 로그아웃.

인증 화면과의 약속:
- POST /signup
  - 성공: /
  - 실패: /signup?error=<code>
- POST /login
  - 성공: /
  - 실패: /login?error=<code>
- POST /logout
  - 성공: /login

오류 코드:
- duplicate
- invalid_username
- invalid_password
- reserved_username
- bad_credentials
"""

import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.db import get_db
from app.models import User
from app.security import MAX_PASSWORD_BYTES, hash_password, verify_password

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"])


def _valid_username(username: str) -> bool:
    """username이 DB 컬럼 범위에 맞는지 확인한다."""
    username = username.strip()
    return 1 <= len(username) <= 50


def _valid_password(password: str) -> bool:
    """빈 비밀번호와 bcrypt 최대 길이 초과를 막는다."""
    if not password:
        return False

    return len(password.encode("utf-8")) <= MAX_PASSWORD_BYTES


@router.post("/signup")
def signup(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    db: DbSession = Depends(get_db),
):
    username = username.strip()

    if username.lower() == "admin":
        logger.info(
            "signup_failed reason=reserved_username username=%s",
            username,
        )
        return RedirectResponse(
            "/signup?error=reserved_username",
            status_code=303,
        )

    if not _valid_username(username):
        logger.info("signup_failed reason=invalid_username")
        return RedirectResponse(
            "/signup?error=invalid_username",
            status_code=303,
        )

    if not _valid_password(password):
        logger.info(
            "signup_failed reason=invalid_password username=%s",
            username,
        )
        return RedirectResponse(
            "/signup?error=invalid_password",
            status_code=303,
        )

    existing_user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if existing_user is not None:
        logger.info(
            "signup_failed reason=duplicate username=%s",
            username,
        )
        return RedirectResponse(
            "/signup?error=duplicate",
            status_code=303,
        )

    user = User(
        username=username,
        password_hash=hash_password(password),
    )

    db.add(user)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        logger.info(
            "signup_failed reason=duplicate username=%s",
            username,
        )
        return RedirectResponse(
            "/signup?error=duplicate",
            status_code=303,
        )

    request.session["user_id"] = user.id

    logger.info(
        "signup_success user_id=%s username=%s",
        user.id,
        user.username,
    )

    return RedirectResponse("/", status_code=303)


@router.post("/login")
def login(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    db: DbSession = Depends(get_db),
):
    username = username.strip()

    user = (
        db.query(User)
        .filter(User.username == username)
        .first()
    )

    if user is None or not verify_password(password, user.password_hash):
        logger.info(
            "login_failed username=%s",
            username,
        )
        return RedirectResponse(
            "/login?error=bad_credentials",
            status_code=303,
        )

    request.session["user_id"] = user.id

    logger.info(
        "login_success user_id=%s username=%s",
        user.id,
        user.username,
    )

    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    user_id = request.session.get("user_id")

    request.session.clear()

    logger.info("logout user_id=%s", user_id)

    return RedirectResponse("/login", status_code=303)