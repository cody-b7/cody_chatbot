"""요청/응답 계약. 이 파일이 곧 API 명세의 원본이다."""

import unicodedata
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import settings
from app.scenarios import KEYS as SCENARIOS  # 정의는 app/scenarios.py 한 곳에만


def _strip_control_chars(text: str) -> str:
    """제어 문자를 걷어낸다. 줄바꿈과 탭은 남긴다.

    널 바이트 같은 제어 문자가 섞이면 로그가 깨져서 추적이 어려워지고,
    DB 에 들어간 뒤 조회 도구마다 다르게 보인다. 입구에서 정리한다.
    """
    keep = {chr(10), chr(9)}  # 줄바꿈, 탭
    return "".join(
        ch for ch in text if ch in keep or unicodedata.category(ch) != "Cc"
    )


class ChatRequest(BaseModel):
    message: str = Field(..., description="사용자의 영어 발화")
    scenario: str = Field(default="cafe", description=f"{SCENARIOS}")
    session_id: int | None = Field(
        default=None,
        gt=0,
        description="이어서 대화할 세션. 없으면 새 세션을 연다.",
    )

    @field_validator("message")
    @classmethod
    def _clean_message(cls, v: str) -> str:
        v = _strip_control_chars(v).strip()
        if not v:
            raise ValueError("메시지를 입력해 주세요.")
        if len(v) > settings.MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"메시지는 {settings.MAX_MESSAGE_LENGTH}자를 넘을 수 없습니다."
            )
        return v

    @field_validator("scenario")
    @classmethod
    def _scenario_known(cls, v: str) -> str:
        if v not in SCENARIOS:
            raise ValueError(f"지원하지 않는 상황입니다. 가능한 값: {', '.join(SCENARIOS)}")
        return v


class ChatResponse(BaseModel):
    session_id: int
    chat_id: int
    scenario: str                   # 이어하기 때 클라이언트가 상황을 알 수 있게
    reply: str                      # 상대역의 응답
    correction: str | None = None   # 표현 교정 (없을 수 있음)


class ChatLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    question: str
    answer: str
    correction: str | None
    created_at: datetime


class CorrectionItem(BaseModel):
    """교정 한 건. 어떤 상황에서 무슨 말을 하다 지적받았는지를 함께 보여준다.

    교정 문구만 나열하면 "왜 틀렸는지"의 맥락이 빠져서 복습이 안 된다.
    """

    id: int
    session_id: int
    scenario: str
    question: str
    correction: str
    created_at: datetime


class SessionSummary(BaseModel):
    """세션 목록 한 줄. 기록 화면에서 "언제 무슨 상황을 연습했나"를 보여준다."""

    id: int
    scenario: str
    created_at: datetime
    turn_count: int
    correction_count: int
    last_message_at: datetime | None


class SessionDetail(BaseModel):
    """세션 하나와 그 안의 대화 전체. 이어하기 화면이 과거 맥락을 복원할 때 쓴다."""

    id: int
    scenario: str
    created_at: datetime
    turns: list[ChatLogItem]


class LearningStats(BaseModel):
    """학습 요약. 교정이 몇 번 붙었는지가 핵심 지표다."""

    total_sessions: int
    total_turns: int
    total_corrections: int
    error_count: int
    avg_latency_ms: int | None


class ErrorResponse(BaseModel):
    error: str    # AI_TIMEOUT / AI_ERROR / INVALID_INPUT
    message: str  # 사용자에게 그대로 보여줄 안내 문구
