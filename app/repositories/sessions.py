"""롤플레이 세션과 대화 기록 접근. 모든 조회는 user_id 로 거른다."""

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.db.models import ChatLog, RoleplaySession


def create(db: Session, user_id: int, scenario: str) -> RoleplaySession:
    session = RoleplaySession(user_id=user_id, scenario=scenario)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get(db: Session, session_id: int) -> RoleplaySession | None:
    return db.get(RoleplaySession, session_id)


def list_summaries(db: Session, user_id: int, limit: int):
    """세션 목록과 세션별 턴 수·교정 수·마지막 대화 시각을 쿼리 한 번으로 집계한다."""
    return (
        db.query(
            RoleplaySession.id,
            RoleplaySession.scenario,
            RoleplaySession.created_at,
            func.count(ChatLog.id).label("turn_count"),
            func.count(ChatLog.correction).label("correction_count"),
            func.max(ChatLog.created_at).label("last_message_at"),
        )
        .outerjoin(
            ChatLog,
            and_(ChatLog.session_id == RoleplaySession.id, ChatLog.error_code.is_(None)),
        )
        .filter(RoleplaySession.user_id == user_id)
        .group_by(RoleplaySession.id)
        .order_by(RoleplaySession.id.desc())
        .limit(limit)
        .all()
    )


def turns(db: Session, session_id: int, last: int | None = None) -> list[ChatLog]:
    """성공한 턴만 오래된 순으로. last 를 주면 최근 last 개만 (프롬프트 문맥용)."""
    query = db.query(ChatLog).filter(
        ChatLog.session_id == session_id, ChatLog.error_code.is_(None)
    )
    if last is None:
        return query.order_by(ChatLog.id).all()
    return list(reversed(query.order_by(ChatLog.id.desc()).limit(last).all()))


def save_log(db: Session, log: ChatLog) -> None:
    db.add(log)
    db.commit()


def list_corrections(db: Session, user_id: int, scenario: str | None, limit: int):
    query = (
        db.query(ChatLog, RoleplaySession.scenario)
        .join(RoleplaySession, RoleplaySession.id == ChatLog.session_id)
        .filter(ChatLog.user_id == user_id, ChatLog.correction.isnot(None))
    )
    if scenario:
        query = query.filter(RoleplaySession.scenario == scenario)
    return query.order_by(ChatLog.id.desc()).limit(limit).all()


def stats(db: Session, user_id: int) -> tuple[int, int, int, dict[str, int]]:
    """(세션 수, 턴 수, 교정 수, 상황별 교정 수)."""
    sessions = (
        db.query(func.count(RoleplaySession.id)).filter(RoleplaySession.user_id == user_id).scalar()
    )
    turns_, corrections = (
        db.query(func.count(ChatLog.id), func.count(ChatLog.correction))
        .filter(ChatLog.user_id == user_id, ChatLog.error_code.is_(None))
        .one()
    )
    by_scenario = (
        db.query(RoleplaySession.scenario, func.count(ChatLog.id))
        .join(ChatLog, ChatLog.session_id == RoleplaySession.id)
        .filter(ChatLog.user_id == user_id, ChatLog.correction.isnot(None))
        .group_by(RoleplaySession.scenario)
        .order_by(func.count(ChatLog.id).desc())
        .all()
    )
    return sessions, turns_, corrections, dict(by_scenario)
