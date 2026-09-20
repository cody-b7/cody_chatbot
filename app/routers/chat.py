"""챗 파이프라인: 질문 수신 -> 컨텍스트 조립 -> AI 호출 -> DB 저장 -> 응답."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.models import ChatLog, RoleplaySession, User
from app.schemas import ChatRequest, ChatResponse
from app.services import context
from app.services.ai import AIError, generate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["chat"])


def _get_or_create_session(
    db: DbSession, user: User, session_id: int | None, scenario: str
) -> RoleplaySession:
    if session_id is not None:
        session = db.get(RoleplaySession, session_id)
        # 남의 세션을 이어쓰지 못하게 소유자를 확인한다
        if session is None or session.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
        return session

    session = RoleplaySession(user_id=user.id, scenario=scenario)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = _get_or_create_session(db, user, payload.session_id, payload.scenario)
    messages = context.build_messages(db, session, payload.message)

    try:
        reply, correction, latency_ms = generate(messages)
    except AIError as exc:
        # 실패도 로그로 남긴다 — 나중에 원인 추적이 가능해야 하므로
        _save(
            db,
            ChatLog(
                user_id=user.id,
                session_id=session.id,
                question=payload.message,
                answer="",
                error_code=exc.code,
                model=settings.AI_MODEL,
            ),
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": exc.code, "message": exc.message},
        )

    log = ChatLog(
        user_id=user.id,
        session_id=session.id,
        question=payload.message,
        answer=reply,
        correction=correction,
        model=settings.AI_MODEL,
        latency_ms=latency_ms,
    )
    saved = _save(db, log)
    if not saved:
        # 저장에 실패해도 사용자는 답을 받아야 한다
        return ChatResponse(
            session_id=session.id,
            chat_id=-1,
            scenario=session.scenario,
            reply=reply,
            correction=correction,
        )

    return ChatResponse(
        session_id=session.id,
        chat_id=log.id,
        scenario=session.scenario,
        reply=reply,
        correction=correction,
    )


def _save(db: DbSession, log: ChatLog) -> bool:
    try:
        db.add(log)
        db.commit()
        db.refresh(log)
    except SQLAlchemyError:
        db.rollback()
        logger.exception("db_save_failed user_id=%s session_id=%s", log.user_id, log.session_id)
        return False
    logger.info("db_save_success user_id=%s chat_id=%s", log.user_id, log.id)
    return True
