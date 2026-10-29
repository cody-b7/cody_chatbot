"""요청/응답 계약. 이 파일이 곧 API 명세의 원본이다."""

import unicodedata
from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

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


def _as_utc(value: datetime) -> datetime:
    """시간대 없는 시각을 UTC 로 표시한다.

    DB 에는 UTC 로 저장하지만 SQLite 는 시간대 정보를 보관하지 않아서,
    읽어 오면 "2026-10-29T07:57:00" 처럼 시간대가 빠진다. 그대로 내보내면
    브라우저가 이를 한국 시간으로 해석해 9시간 이르게 표시한다.
    "+00:00" 을 붙여 내보내면 브라우저가 사용자 시간대로 바르게 바꿔 보여준다.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


# API 로 나가는 모든 시각에 쓴다
UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]


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
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "session_id": 12,
                "chat_id": 87,
                "saved": True,
                "scenario": "cafe",
                "reply": "Sure! What size would you like?",
                "correction": '"I want coffee" 보다 "Could I get a coffee?" 가 더 자연스러워요.',
            }
        }
    )

    session_id: int
    chat_id: int | None             # 기록 저장에 실패하면 None
    saved: bool                     # 기록이 DB 에 저장됐는지
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
    created_at: UtcDatetime


class ChatLogEntry(ChatLogItem):
    """로그 조회용 한 줄. 실패한 턴도 error_code 와 함께 그대로 보여준다."""

    error_code: str | None
    latency_ms: int | None


class CorrectionItem(BaseModel):
    """교정 한 건. 어떤 상황에서 무슨 말을 하다 지적받았는지를 함께 보여준다.

    교정 문구만 나열하면 "왜 틀렸는지"의 맥락이 빠져서 복습이 안 된다.
    """

    id: int
    session_id: int
    scenario: str
    question: str
    correction: str
    created_at: UtcDatetime


class SessionSummary(BaseModel):
    """세션 목록 한 줄. 기록 화면에서 "언제 무슨 상황을 연습했나"를 보여준다."""

    id: int
    scenario: str
    created_at: UtcDatetime
    turn_count: int
    correction_count: int
    last_message_at: UtcDatetime | None


class SessionDetail(BaseModel):
    """세션 하나와 그 안의 대화 전체. 이어하기 화면이 과거 맥락을 복원할 때 쓴다."""

    id: int
    scenario: str
    created_at: UtcDatetime
    turns: list[ChatLogItem]


class LearningStats(BaseModel):
    """학습 요약. 교정이 몇 번 붙었는지가 핵심 지표다."""

    total_sessions: int
    total_turns: int
    total_corrections: int
    error_count: int
    avg_latency_ms: int | None
    # 상황별 교정 횟수 (많은 순). 교정 화면의 필터에 쓴다.
    corrections_by_scenario: dict[str, int]


class ErrorResponse(BaseModel):
    """모든 오류 응답의 공통 형식. 화면은 message 만 보여주면 된다."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"error": "AI_TIMEOUT", "message": "현재 응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요."}
        }
    )

    error: str    # 오류 코드. README 의 상태코드 표 참고
    message: str  # 사용자에게 그대로 보여줄 안내 문구
