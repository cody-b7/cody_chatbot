"""DB 스키마. 이 파일은 A가 소유한다 — 필드 추가는 A에게 요청할 것.

roleplay_sessions 를 둔 이유:
  컨텍스트를 '세션 단위'로 끊기 위해서다. 카페 롤플레이를 하다가
  공항 롤플레이로 넘어가면 앞 대화는 문맥에서 빠져야 한다.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    sessions: Mapped[list["RoleplaySession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    chat_logs: Mapped[list["ChatLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class RoleplaySession(Base):
    """롤플레이 한 판. 문맥 유지의 단위."""

    __tablename__ = "roleplay_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    scenario: Mapped[str] = mapped_column(String(30))  # cafe / airport / ...
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="sessions")
    chat_logs: Mapped[list["ChatLog"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ChatLog(Base):
    """대화 1턴. 요건 최소 필드(사용자·시각·질문·응답)를 모두 포함한다."""

    __tablename__ = "chat_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("roleplay_sessions.id"), index=True
    )

    question: Mapped[str] = mapped_column(Text)           # 사용자 발화
    answer: Mapped[str] = mapped_column(Text)             # 상대역 응답
    correction: Mapped[str | None] = mapped_column(Text, nullable=True)  # 표현 교정

    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    user: Mapped["User"] = relationship(back_populates="chat_logs")
    session: Mapped["RoleplaySession"] = relationship(back_populates="chat_logs")
