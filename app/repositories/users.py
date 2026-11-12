"""사용자 테이블 접근."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import User

# 대소문자만 다른 기존 계정이 여럿일 때 비밀번호를 대조해 볼 최대 개수 (bcrypt 비용 제한)
MAX_CASE_VARIANTS = 5


def find_exact(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def find_case_variants(db: Session, normalized: str) -> list[User]:
    """대소문자만 다른 계정들. 정규화 규칙이 생기기 전에 'Tester' 처럼 가입한 계정도 찾는다."""
    return (
        db.query(User)
        .filter(func.lower(User.username) == normalized)
        .order_by(User.id)
        .limit(MAX_CASE_VARIANTS)
        .all()
    )


def create(db: Session, username: str, password_hash: str) -> User:
    user = User(username=username, password_hash=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
