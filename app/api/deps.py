"""라우트가 공통으로 쓰는 의존성 (인증·인가)."""

import logging

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.logging import Event
from app.db.models import User
from app.db.session import get_db

logger = logging.getLogger("cody.auth")


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """로그인한 사용자. 비로그인이면 401 (브라우저 화면 요청은 /login 으로 이동)."""
    user_id = request.session.get("user_id")
    user = db.get(User, user_id) if user_id is not None else None
    if user is not None:
        return user

    if user_id is not None:
        # 쿠키는 있는데 계정이 없다. 비우지 않으면 /login 이 "로그인됨"으로 보고 / 로 돌려보내
        # 사용자가 빠져나올 수 없다.
        request.session.clear()
        logger.info("%s user_id=%s", Event.STALE_SESSION, user_id)
    raise AppError(401, "UNAUTHORIZED", "로그인이 필요합니다.")


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise AppError(403, "FORBIDDEN", "관리자 권한이 필요합니다.")
    return user
