"""회원가입과 로그인 판정."""

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import Event
from app.core.security import (
    check_password,
    check_username,
    hash_password,
    normalize_username,
    verify_password,
)
from app.db.models import User
from app.repositories import users as user_repo

logger = logging.getLogger("cody.auth")

# 없는 아이디로 로그인할 때도 bcrypt 한 번만큼 시간을 쓰기 위한 비교용 해시.
# 바로 돌려주면 응답 속도만으로 가입 여부를 알 수 있다 (있는 아이디 ~600ms, 없는 아이디 ~5ms).
_DUMMY_HASH = hash_password("timing-equalizer-0")


def register(db: Session, raw_username: str, password: str) -> tuple[User | None, str | None]:
    """(가입한 사용자, None) 또는 (None, 오류 코드)."""
    username = normalize_username(raw_username)
    error = check_username(username) or check_password(password, username)
    if not error and user_repo.find_case_variants(db, username):
        error = "duplicate"
    if error:
        logger.info("%s reason=%s", Event.SIGNUP_FAILED, error)
        return None, error

    try:
        user = user_repo.create(db, username, hash_password(password))
    except IntegrityError:  # 확인한 사이에 같은 아이디가 먼저 가입된 경우
        db.rollback()
        logger.info("%s reason=duplicate", Event.SIGNUP_FAILED)
        return None, "duplicate"
    logger.info("%s user_id=%s", Event.SIGNUP_SUCCESS, user.id)
    return user, None


def authenticate(db: Session, raw_username: str, password: str) -> User | None:
    """아이디·비밀번호가 맞는 계정. 없는 아이디와 틀린 비밀번호는 똑같이 None.

    정규화 규칙이 생기기 전에 가입한 계정 때문에 두 단계로 찾는다.
      1) 입력과 정확히 같은 아이디가 있으면 그 계정만 본다 (Tester 와 tester 가 따로 있어도 각자 로그인)
      2) 없으면 대소문자만 다른 계정 중 비밀번호가 맞는 계정으로 로그인한다
    """
    entered = raw_username.strip()
    exact = user_repo.find_exact(db, entered) if entered else None
    candidates = [exact] if exact else user_repo.find_case_variants(db, normalize_username(entered))
    if not candidates:
        verify_password(password, _DUMMY_HASH)

    user = next((u for u in candidates if verify_password(password, u.password_hash)), None)
    event = Event.LOGIN_SUCCESS if user else Event.LOGIN_FAILED
    logger.info("%s user_id=%s", event, getattr(user, "id", None))
    return user
