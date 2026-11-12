"""학습 기록: 받은 교정 모음과 요약 통계."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.repositories import sessions as session_repo
from app.schemas.common import ErrorResponse
from app.schemas.learning import CorrectionItem, LearningStats

router = APIRouter(
    prefix="/api",
    tags=["learning"],
    responses={401: {"model": ErrorResponse, "description": "로그인하지 않음"}},
)


@router.get("/corrections", response_model=list[CorrectionItem], summary="내가 받은 교정")
def list_corrections(
    scenario: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = session_repo.list_corrections(db, user.id, scenario, limit)
    return [
        CorrectionItem(
            session_id=log.session_id, scenario=scn, question=log.question,
            correction=log.correction, created_at=log.created_at,
        )
        for log, scn in rows
    ]


@router.get("/stats", response_model=LearningStats, summary="내 학습 요약")
def get_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sessions, turns, corrections, by_scenario = session_repo.stats(db, user.id)
    return LearningStats(
        total_sessions=sessions, total_turns=turns,
        total_corrections=corrections, corrections_by_scenario=by_scenario,
    )
