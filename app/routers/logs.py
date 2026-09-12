"""대화 로그 조회. 사용자는 자기 로그만 볼 수 있다."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.db import get_db
from app.deps import get_current_user
from app.models import ChatLog, User
from app.schemas import ChatLogItem

router = APIRouter(prefix="/api/me", tags=["logs"])


@router.get("/chats", response_model=list[ChatLogItem])
def my_chats(
    limit: int = Query(default=50, ge=1, le=200),
    session_id: int | None = None,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(ChatLog).filter(ChatLog.user_id == user.id)
    if session_id is not None:
        q = q.filter(ChatLog.session_id == session_id)
    return q.order_by(ChatLog.id.desc()).limit(limit).all()


@router.get("/corrections", response_model=list[ChatLogItem])
def my_corrections(
    limit: int = Query(default=50, ge=1, le=200),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """교정이 달린 턴만. '내가 자주 틀리는 표현' 화면의 데이터."""
    return (
        db.query(ChatLog)
        .filter(ChatLog.user_id == user.id, ChatLog.correction.isnot(None))
        .order_by(ChatLog.id.desc())
        .limit(limit)
        .all()
    )
