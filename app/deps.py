"""공용 의존성.

get_current_user 의 시그니처와 반환 타입은 고정이다.
B가 내부 구현만 교체하고, C의 라우터는 손대지 않는다.
"""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DbSession

from app.config import settings
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

    # 인증이 붙기 전까지 A·C가 막히지 않도록 하는 개발용 우회.
    # DEV_AUTH_BYPASS=false 가 기본이라 배포 환경에서는 절대 타지 않는다.
    # TODO(B): 세션 쿠키 검증을 완성한 뒤 이 블록을 삭제할 것.
    if settings.DEV_AUTH_BYPASS:
        user = db.query(User).order_by(User.id).first()
        if user is not None:
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="로그인이 필요합니다.",
    )
