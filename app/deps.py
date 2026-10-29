"""공용 의존성."""

import logging

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DbSession

from app.db import get_db
from app.log_events import Event
from app.models import User

logger = logging.getLogger("cody.auth")


def get_current_user(
    request: Request,
    db: DbSession = Depends(get_db),
) -> User:
    """로그인한 사용자를 반환한다. 비로그인이면 401."""
    user_id = request.session.get("user_id")

    if user_id is not None:
        user = db.get(User, user_id)
        if user is not None:
            return user

        # 쿠키는 있는데 계정이 없다 (계정 삭제, DB 초기화 등).
        # 세션을 비워 두지 않으면 /login 은 "로그인됨"으로 보고 / 로 보내고,
        # / 는 다시 401 을 내서 사용자가 빠져나올 수 없다.
        request.session.clear()
        logger.info("%s user_id=%s", Event.STALE_SESSION, user_id)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="로그인이 필요합니다.",
    )


def get_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    """관리자 사용자를 반환한다. 관리자가 아니면 403."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )

    return user
