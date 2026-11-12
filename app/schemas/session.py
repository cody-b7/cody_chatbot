"""세션·메시지 요청과 응답."""

import unicodedata

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import settings
from app.core.scenarios import BY_KEY
from app.schemas.common import UtcDatetime


class SessionCreate(BaseModel):
    scenario: str = Field(description=f"상황 키: {', '.join(BY_KEY)}")

    @field_validator("scenario")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in BY_KEY:
            raise ValueError(f"지원하지 않는 상황입니다. 가능한 값: {', '.join(BY_KEY)}")
        return v


class MessageCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"example": {"message": "I want coffee"}})

    message: str = Field(description="학습자의 영어 발화")

    @field_validator("message")
    @classmethod
    def _clean(cls, v: str) -> str:
        # 널 바이트 같은 제어 문자는 로그를 깨뜨리므로 지운다 (줄바꿈·탭은 남김)
        v = "".join(ch for ch in v if ch in "\n\t" or unicodedata.category(ch) != "Cc").strip()
        if not v:
            raise ValueError("메시지를 입력해 주세요.")
        if len(v) > settings.MAX_MESSAGE_LENGTH:
            raise ValueError(f"메시지는 {settings.MAX_MESSAGE_LENGTH}자를 넘을 수 없습니다.")
        return v


class Turn(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str
    correction: str | None
    created_at: UtcDatetime


class MessageResponse(BaseModel):
    """상대역의 응답. 기록 저장에 실패해도 답은 돌려주고 saved=false 로 알린다."""

    session_id: int
    reply: str
    correction: str | None
    saved: bool


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scenario: str
    created_at: UtcDatetime
    turn_count: int
    correction_count: int
    last_message_at: UtcDatetime | None


class SessionDetail(BaseModel):
    id: int
    scenario: str
    created_at: UtcDatetime
    turns: list[Turn]
