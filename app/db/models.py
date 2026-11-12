"""DB 테이블.

roleplay_sessions 를 두는 이유: 문맥을 '세션 단위'로 끊기 위해서다.
카페 롤플레이에서 공항으로 넘어가면 앞 대화는 문맥에서 빠져야 한다.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)  # scripts/set_admin.py 로만 변경
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sessions: Mapped[list["RoleplaySession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RoleplaySession(Base):
    """롤플레이 한 판. 문맥 유지의 단위."""

    __tablename__ = "roleplay_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    scenario: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="sessions")
    chat_logs: Mapped[list["ChatLog"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ChatLog(Base):
    """대화 1턴. 실패한 턴도 error_code 와 함께 남겨 원인을 추적한다."""

    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("roleplay_sessions.id"), index=True)
    question: Mapped[str] = mapped_column(Text)  # 사용자 발화
    answer: Mapped[str] = mapped_column(Text)  # 상대역 응답 (실패하면 빈 문자열)
    correction: Mapped[str | None] = mapped_column(Text)  # 한국어 교정
    model: Mapped[str | None] = mapped_column(String(100))
    latency_ms: Mapped[int | None]
    error_code: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )

    session: Mapped[RoleplaySession] = relationship(back_populates="chat_logs")
