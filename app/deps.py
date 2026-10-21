"""공용 의존성."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DbSession

from app.db import get_db
from app.models import User


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