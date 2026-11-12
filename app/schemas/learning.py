"""학습 기록(교정 모음, 통계) 응답."""

from pydantic import BaseModel

from app.schemas.common import UtcDatetime


class CorrectionItem(BaseModel):
    """교정 한 건. 어떤 상황에서 무슨 말을 하다 지적받았는지 함께 보여줘야 복습이 된다."""

    session_id: int
    scenario: str
    question: str
    correction: str
    created_at: UtcDatetime


class LearningStats(BaseModel):
    total_sessions: int
    total_turns: int
    total_corrections: int
    corrections_by_scenario: dict[str, int]  # 많은 순. 교정 화면의 필터에 쓴다
