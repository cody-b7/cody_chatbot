"""대화 로그 조회. 사용자는 자기 로그만 볼 수 있다.

요건 4("사용자 기준 로그 조회/추적")를 담당하는 라우터다.
모든 쿼리에 user_id 필터가 들어가며, 남의 기록은 어떤 경로로도 나오지 않는다.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from app.db import get_db
from app.deps import get_current_user
from app.models import ChatLog, RoleplaySession, User
from app.schemas import (
    ChatLogItem,
    CorrectionItem,
    LearningStats,
    SessionDetail,
    SessionSummary,
)

router = APIRouter(prefix="/api/me", tags=["logs"])


@router.get("/chats", response_model=list[ChatLogItem])
def my_chats(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session_id: int | None = None,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """내 대화 기록. session_id 를 주면 그 세션만."""
    q = db.query(ChatLog).filter(ChatLog.user_id == user.id)
    if session_id is not None:
        q = q.filter(ChatLog.session_id == session_id)
    return q.order_by(ChatLog.id.desc()).offset(offset).limit(limit).all()


@router.get("/corrections", response_model=list[CorrectionItem])
def my_corrections(
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


@router.get("/corrections/by-scenario")
def corrections_by_scenario(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, int]:
    """상황별 교정 횟수. 어떤 상황에서 자주 막히는지 보여준다."""
    rows = (
        db.query(RoleplaySession.scenario, func.count(ChatLog.id))
        .join(ChatLog, ChatLog.session_id == RoleplaySession.id)
        .filter(ChatLog.user_id == user.id, ChatLog.correction.isnot(None))
        .group_by(RoleplaySession.scenario)
        .order_by(func.count(ChatLog.id).desc())
        .all()
    )
    return {scenario: count for scenario, count in rows}


@router.get("/sessions", response_model=list[SessionSummary])
def my_sessions(
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


@router.get("/stats", response_model=LearningStats)
def my_stats(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """학습 요약 통계."""
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
    )


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def session_detail(
    session_id: int,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """세션 하나와 그 안의 대화 전체.

    이어하기 화면이 과거 맥락을 복원할 때 쓴다.
    남의 세션은 존재 자체를 알려주지 않기 위해 404 로 돌려준다.
    """
    session = db.get(RoleplaySession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "세션을 찾을 수 없습니다.")

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
