"""롤플레이 세션과 메시지 (REST 자원).

  POST /api/sessions                    세션 시작 (상황 선택)
  GET  /api/sessions                    내 세션 목록
  GET  /api/sessions/{id}               세션 하나의 대화 (기록 펼치기, 이어하기)
  POST /api/sessions/{id}/messages      말하기 → 상대역 응답과 교정
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.repositories import sessions as session_repo
from app.schemas.common import ErrorResponse
from app.schemas.session import (
    MessageCreate,
    MessageResponse,
    SessionCreate,
    SessionDetail,
    SessionSummary,
)
from app.services import chat as chat_service

router = APIRouter(
    prefix="/api/sessions",
    tags=["sessions"],
    responses={401: {"model": ErrorResponse, "description": "로그인하지 않음"}},
)
_OWNED = {
    403: {"model": ErrorResponse, "description": "남의 세션"},
    404: {"model": ErrorResponse, "description": "없는 세션"},
}


@router.post("", status_code=201, response_model=SessionSummary, summary="세션 시작")
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = session_repo.create(db, user.id, payload.scenario)
    return SessionSummary(
        id=session.id, scenario=session.scenario, created_at=session.created_at,
        turn_count=0, correction_count=0, last_message_at=None,
    )


@router.get("", response_model=list[SessionSummary], summary="내 세션 목록")
def list_sessions(
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return session_repo.list_summaries(db, user.id, limit)


@router.get("/{session_id}", response_model=SessionDetail, responses=_OWNED, summary="세션 대화")
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = chat_service.get_owned_session(db, user, session_id)
    return SessionDetail(
        id=session.id, scenario=session.scenario, created_at=session.created_at,
        turns=session_repo.turns(db, session.id),
    )


@router.post(
    "/{session_id}/messages",
    status_code=201,
    response_model=MessageResponse,
    summary="말하기 (AI 응답과 교정)",
    responses={
        **_OWNED,
        422: {"model": ErrorResponse, "description": "빈 입력, 길이 초과"},
        503: {"model": ErrorResponse, "description": "AI 장애 (Retry-After 헤더 포함)"},
        504: {"model": ErrorResponse, "description": "AI 응답 시간 초과"},
    },
)
def send_message(
    session_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return chat_service.send_message(db, user, session_id, payload.message)
