"""내 학습 기록 조회. 사용자는 자기 기록만 볼 수 있다.

요건 4("사용자 기준 로그 조회/추적")를 담당하는 라우터다.
모든 쿼리에 user_id 필터가 들어가며, 남의 기록은 어떤 경로로도 나오지 않는다.

엔드포인트는 화면이 실제로 쓰는 단위로만 둔다.
  /chats             대화 로그 원본 (실패한 턴 포함) — 추적·운영용
  /sessions          세션 목록 (기록 화면)
  /sessions/{id}     세션 하나의 대화 (기록 화면 펼치기, 이어하기)
  /corrections       교정 모음 (교정 화면)
  /stats             요약 통계 + 상황별 교정 횟수 (기록·교정 화면)

호환용 (배포 전에 열어 둔 화면이 계속 부르는 옛 요청. 문서에 deprecated 로 표시)
  /chats?session_id=           세션 하나의 로그만
  /corrections/by-scenario     상황별 교정 횟수 (지금은 /stats 에 포함)
호출되면 deprecated_api_called 로그를 남긴다. 한동안 이 로그가 없으면 지워도 된다.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from app.db import get_db
from app.deps import get_current_user
from app.log_events import Event
from app.models import ChatLog, RoleplaySession, User
from app.schemas import (
    ChatLogEntry,
    CorrectionItem,
    ErrorResponse,
    LearningStats,
    SessionDetail,
    SessionSummary,
)

logger = logging.getLogger("cody.request")

router = APIRouter(
    prefix="/api/me",
    tags=["records"],
    responses={401: {"model": ErrorResponse, "description": "로그인하지 않음"}},
)


@router.get("/chats", response_model=list[ChatLogEntry], summary="내 대화 로그 (최신순)")
def list_my_chat_logs(
    response: Response,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session_id: int | None = Query(
        default=None,
        deprecated=True,
        description="옛 기록 화면 호환용. 새 화면은 /api/me/sessions/{session_id} 를 쓴다.",
    ),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """대화 로그 원본. AI 호출에 실패한 턴도 error_code 와 함께 나온다."""
    q = db.query(ChatLog).filter(ChatLog.user_id == user.id)
    if session_id is not None:
        # 이 필터를 없애면 옛 화면의 요청이 모든 세션의 로그를 받아 기록이 섞인다
        _mark_deprecated(response, "/api/me/chats?session_id", user)
        q = q.filter(ChatLog.session_id == session_id)
    return q.order_by(ChatLog.id.desc()).offset(offset).limit(limit).all()


@router.get("/corrections", response_model=list[CorrectionItem], summary="내가 받은 교정")
def list_my_corrections(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    scenario: str | None = None,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """교정이 달린 턴만. '내가 자주 틀리는 표현' 화면의 데이터.

    세션을 조인해 상황(scenario)까지 함께 내려준다. 교정 문구만 나열하면
    어떤 맥락에서 틀린 말인지 알 수 없어 복습이 되지 않는다.
    """
    q = (
        db.query(ChatLog, RoleplaySession.scenario)
        .join(RoleplaySession, RoleplaySession.id == ChatLog.session_id)
        .filter(ChatLog.user_id == user.id, ChatLog.correction.isnot(None))
    )
    if scenario is not None:
        q = q.filter(RoleplaySession.scenario == scenario)

    rows = q.order_by(ChatLog.id.desc()).offset(offset).limit(limit).all()
    return [
        CorrectionItem(
            id=log.id,
            session_id=log.session_id,
            scenario=scn,
            question=log.question,
            correction=log.correction,
            created_at=log.created_at,
        )
        for log, scn in rows
    ]


@router.get("/sessions", response_model=list[SessionSummary], summary="내 연습 세션 목록")
def list_my_sessions(
    limit: int = Query(default=30, ge=1, le=100),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """내 롤플레이 세션 목록.

    한 번의 쿼리로 세션별 턴 수·교정 수·마지막 대화 시각까지 집계한다.
    세션마다 따로 조회하면 목록이 길어질수록 쿼리가 선형으로 늘어난다.
    """
    rows = (
        db.query(
            RoleplaySession.id,
            RoleplaySession.scenario,
            RoleplaySession.created_at,
            func.count(ChatLog.id).label("turn_count"),
            func.count(ChatLog.correction).label("correction_count"),
            func.max(ChatLog.created_at).label("last_message_at"),
        )
        .outerjoin(ChatLog, ChatLog.session_id == RoleplaySession.id)
        .filter(RoleplaySession.user_id == user.id)
        .group_by(RoleplaySession.id)
        .order_by(RoleplaySession.id.desc())
        .limit(limit)
        .all()
    )
    return [
        SessionSummary(
            id=r.id,
            scenario=r.scenario,
            created_at=r.created_at,
            turn_count=r.turn_count,
            correction_count=r.correction_count,
            last_message_at=r.last_message_at,
        )
        for r in rows
    ]


@router.get("/stats", response_model=LearningStats, summary="내 학습 요약 통계")
def get_my_stats(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """학습 요약 통계와 상황별 교정 횟수.

    상황별 교정 횟수는 원래 별도 엔드포인트였지만, 같은 "요약" 성격이라
    여기에 합쳤다. 화면이 부르는 API 수가 하나 줄어든다.
    """
    total_sessions = (
        db.query(func.count(RoleplaySession.id))
        .filter(RoleplaySession.user_id == user.id)
        .scalar()
        or 0
    )

    turns, corrections, errors, avg_latency = (
        db.query(
            func.count(ChatLog.id),
            func.count(ChatLog.correction),
            func.count(ChatLog.error_code),
            func.avg(ChatLog.latency_ms),
        )
        .filter(ChatLog.user_id == user.id)
        .one()
    )

    return LearningStats(
        total_sessions=total_sessions,
        total_turns=turns or 0,
        total_corrections=corrections or 0,
        error_count=errors or 0,
        avg_latency_ms=round(avg_latency) if avg_latency is not None else None,
        corrections_by_scenario=_corrections_by_scenario(db, user),
    )


@router.get(
    "/corrections/by-scenario",
    response_model=dict[str, int],
    deprecated=True,
    summary="상황별 교정 횟수 (옛 화면 호환용)",
)
def corrections_by_scenario_legacy(
    response: Response,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """배포 전에 열어 둔 교정 화면이 부르는 옛 경로. 새 화면은 /api/me/stats 를 쓴다."""
    _mark_deprecated(response, "/api/me/corrections/by-scenario", user)
    return _corrections_by_scenario(db, user)


def _corrections_by_scenario(db: DbSession, user: User) -> dict[str, int]:
    """상황별 교정 횟수 (많은 순)."""
    rows = (
        db.query(RoleplaySession.scenario, func.count(ChatLog.id))
        .join(ChatLog, ChatLog.session_id == RoleplaySession.id)
        .filter(ChatLog.user_id == user.id, ChatLog.correction.isnot(None))
        .group_by(RoleplaySession.scenario)
        .order_by(func.count(ChatLog.id).desc())
        .all()
    )
    return {scenario: count for scenario, count in rows}


def _mark_deprecated(response: Response, api: str, user: User) -> None:
    """옛 요청임을 응답 헤더와 로그로 남긴다. 로그가 끊기면 호환 경로를 지울 시점이다."""
    response.headers["Deprecation"] = "true"
    logger.info("%s api=%s user_id=%s", Event.DEPRECATED_API_CALLED, api, user.id)


@router.get(
    "/sessions/{session_id}",
    response_model=SessionDetail,
    summary="세션 하나의 대화 전체",
    responses={
        403: {"model": ErrorResponse, "description": "남의 세션"},
        404: {"model": ErrorResponse, "description": "없는 세션"},
    },
)
def get_my_session(
    session_id: int,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """세션 하나와 그 안의 대화 전체.

    기록 화면의 펼치기와 이어하기 화면이 함께 쓴다.
    남의 세션은 403 (로그인은 했지만 권한이 없음). /api/chat 과 같은 기준이다.
    """
    session = db.get(RoleplaySession, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")
    if session.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "이 대화에 접근할 권한이 없습니다.")

    turns = (
        db.query(ChatLog)
        .filter(ChatLog.session_id == session.id, ChatLog.error_code.is_(None))
        .order_by(ChatLog.id)
        .all()
    )
    return SessionDetail(
        id=session.id,
        scenario=session.scenario,
        created_at=session.created_at,
        turns=turns,
    )
