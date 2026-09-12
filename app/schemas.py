"""요청/응답 계약. 이 파일이 곧 API 명세의 원본이다."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import settings

# 롤플레이 시나리오. 추가하려면 services/context.py 의 설명도 같이 넣을 것.
SCENARIOS: tuple[str, ...] = (
    "cafe",
    "restaurant",
    "airport",
    "shopping",
    "smalltalk",
)


class ChatRequest(BaseModel):
    message: str = Field(..., description="사용자의 영어 발화")
    scenario: str = Field(default="cafe", description=f"{SCENARIOS}")
    session_id: int | None = Field(
        default=None, description="이어서 대화할 세션. 없으면 새 세션을 연다."
    )

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, v: str) -> str:
        v = v.strip()
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


class ErrorResponse(BaseModel):
    error: str    # AI_TIMEOUT / AI_ERROR / INVALID_INPUT
    message: str  # 사용자에게 그대로 보여줄 안내 문구
