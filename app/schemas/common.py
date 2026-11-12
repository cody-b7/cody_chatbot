"""여러 스키마가 함께 쓰는 타입."""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import AfterValidator, BaseModel


def _as_utc(value: datetime) -> datetime:
    """SQLite 는 시간대를 저장하지 않는다. 시간대 없이 내보내면 브라우저가
    한국 시간으로 해석해 9시간 이르게 보이므로 UTC 표시를 붙인다."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


UtcDatetime = Annotated[datetime, AfterValidator(_as_utc)]


class ErrorResponse(BaseModel):
    """모든 오류 응답의 형식. 화면은 message 만 보여주면 된다."""

    error: str
    message: str
