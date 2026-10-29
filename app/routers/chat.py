"""챗 파이프라인: 질문 수신 -> 컨텍스트 조립 -> AI 호출 -> DB 저장 -> 응답."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session as DbSession

from app.config import settings
from app.db import get_db
from app.deps import get_current_user
from app.log_events import Event
from app.models import ChatLog, RoleplaySession, User
from app.schemas import ChatRequest, ChatResponse, ErrorResponse
from app.services import context
from app.services.ai import AIError, generate_ai_reply

logger = logging.getLogger("cody.db")
router = APIRouter(prefix="/api", tags=["chat"])

# AI 실패 코드 → HTTP 상태코드
#   타임아웃은 "상류 서버가 제때 답하지 않음" 이므로 504,
#   그 밖의 장애는 "지금은 처리할 수 없음" 이므로 503 + Retry-After.
_AI_ERROR_STATUS = {
    "AI_TIMEOUT": status.HTTP_504_GATEWAY_TIMEOUT,
    "AI_ERROR": status.HTTP_503_SERVICE_UNAVAILABLE,
}
_RETRY_AFTER_SECONDS = "5"


def _get_or_create_session(
    db: DbSession, user: User, session_id: int | None, scenario: str
) -> RoleplaySession:
    if session_id is not None:
        session = db.get(RoleplaySession, session_id)
        if session is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
        # 남의 세션을 이어쓰지 못하게 소유자를 확인한다.
        # 로그인은 했지만 이 세션에 대한 권한이 없으므로 403 (인증 401 과 구분되는 인가 실패)
        if session.user_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "이 대화에 접근할 권한이 없습니다.")
        return session

    session = RoleplaySession(user_id=user.id, scenario=scenario)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="상대역에게 말하고 응답과 교정을 받는다",
    responses={
        401: {"model": ErrorResponse, "description": "로그인하지 않음"},
        403: {"model": ErrorResponse, "description": "남의 세션"},
        404: {"model": ErrorResponse, "description": "없는 세션"},
        422: {"model": ErrorResponse, "description": "입력 검증 실패 (빈 입력, 길이 초과, 미지원 상황)"},
        503: {"model": ErrorResponse, "description": "AI 게이트웨이 장애 (Retry-After 헤더 포함)"},
        504: {"model": ErrorResponse, "description": "AI 응답 시간 초과"},
    },
)
def send_message(
    payload: ChatRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = _get_or_create_session(db, user, payload.session_id, payload.scenario)
    messages = context.build_prompt_messages(db, session, payload.message)

    try:
        ai_reply = generate_ai_reply(messages)
    except AIError as exc:
        # 실패도 로그로 남긴다 — 나중에 원인 추적이 가능해야 하므로
        _save_chat_log(
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
        status_code = _AI_ERROR_STATUS.get(exc.code, status.HTTP_503_SERVICE_UNAVAILABLE)
        headers = (
            {"Retry-After": _RETRY_AFTER_SECONDS}
            if status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            else None
        )
        return JSONResponse(
            status_code=status_code,
            content={"error": exc.code, "message": exc.message},
            headers=headers,
        )

    log = ChatLog(
        user_id=user.id,
        session_id=session.id,
        question=payload.message,
        answer=ai_reply.reply,
        correction=ai_reply.correction,
        model=settings.AI_MODEL,
        latency_ms=ai_reply.latency_ms,
    )
    # 저장에 실패해도 사용자는 답을 받아야 한다. 대신 saved=False 로 알린다.
    saved = _save_chat_log(db, log)

    return ChatResponse(
        session_id=session.id,
        chat_id=log.id if saved else None,
        saved=saved,
        scenario=session.scenario,
        reply=ai_reply.reply,
        correction=ai_reply.correction,
    )


def _save_chat_log(db: DbSession, log: ChatLog) -> bool:
    """대화 한 턴을 저장한다. 실패하면 롤백하고 False."""
    try:
        db.add(log)
        db.commit()
        db.refresh(log)
    except SQLAlchemyError:
        db.rollback()
        logger.exception(
            "%s user_id=%s session_id=%s", Event.DB_SAVE_FAILED, log.user_id, log.session_id
        )
        return False
    logger.info("%s user_id=%s chat_id=%s", Event.DB_SAVE_SUCCESS, log.user_id, log.id)
    return True
