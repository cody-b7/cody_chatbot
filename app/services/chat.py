"""대화 흐름: 세션 확인 → 프롬프트 구성 → AI 호출 → 기록 저장."""

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import Event
from app.db.models import ChatLog, RoleplaySession, User
from app.repositories import sessions as session_repo
from app.schemas.session import MessageResponse
from app.services.ai_client import generate_ai_reply
from app.services.prompt import build_prompt_messages

logger = logging.getLogger("cody.db")


def get_owned_session(db: Session, user: User, session_id: int) -> RoleplaySession:
    """없는 세션은 404, 남의 세션은 403 (로그인은 했지만 권한이 없음)."""
    session = session_repo.get(db, session_id)
    if session is None:
        raise AppError(404, "NOT_FOUND", "세션을 찾을 수 없습니다.")
    if session.user_id != user.id:
        raise AppError(403, "FORBIDDEN", "이 대화에 접근할 권한이 없습니다.")
    return session


def send_message(db: Session, user: User, session_id: int, message: str) -> MessageResponse:
    session = get_owned_session(db, user, session_id)
    history = session_repo.turns(db, session.id, last=settings.AI_MAX_CONTEXT_TURNS)
    log = ChatLog(user_id=user.id, session_id=session.id, question=message, model=settings.AI_MODEL)

    try:
        ai = generate_ai_reply(build_prompt_messages(session.scenario, history, message))
    except AppError as exc:
        # 실패한 턴도 남겨야 원인을 추적할 수 있다. 문맥에서는 빠진다.
        log.answer, log.error_code = "", exc.code
        _save(db, log)
        raise

    log.answer, log.correction, log.latency_ms = ai.reply, ai.correction, ai.latency_ms
    saved = _save(db, log)  # 저장에 실패해도 사용자는 답을 받는다
    return MessageResponse(
        session_id=session.id, reply=ai.reply, correction=ai.correction, saved=saved
    )


def _save(db: Session, log: ChatLog) -> bool:
    try:
        session_repo.save_log(db, log)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("%s session_id=%s", Event.DB_SAVE_FAILED, log.session_id)
        return False
    logger.info("%s user_id=%s chat_id=%s", Event.DB_SAVE_SUCCESS, log.user_id, log.id)
    return True
