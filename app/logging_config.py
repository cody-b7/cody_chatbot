"""로깅 설정.

한 줄 형식:
  LEVEL 시각(시간대 포함) 로거 request_id=<id> <이벤트> key=value ...
  예) INFO  2026-10-29T16:57:59+09:00 cody.ai request_id=f263576bbbcf ai_call_success latency_ms=1840

- 파일(logs/app.log)과 표준출력(systemd journal) 두 곳에 남는다. 둘 다 디스크에
  쓰므로 서버를 재시작해도 남아 있다. 파일은 5MB 씩 최대 6개(약 30MB)를 보관한다.

- 로거는 분야별로 나눈다: cody.request / cody.auth / cody.ai / cody.db
  분야만 골라 보고 싶으면 `grep " cody.ai "` 처럼 로거 이름으로 거르면 된다.
- request_id 는 요청 미들웨어가 정해 contextvar 에 넣는다. 아래 필터가 모든
  로그 줄에 자동으로 붙이므로, 요청 → AI 호출 → DB 저장을 한 id 로 묶어 볼 수 있다.
- 이벤트 이름은 app/log_events.py 한 곳에서 관리한다.
"""

import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import settings

_FORMAT = "%(levelname)-5s %(asctime)s %(name)s request_id=%(request_id)s %(message)s"

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "app.log"

# 요청 밖(앱 시작, 스크립트)에서 찍히는 로그는 "-" 로 남는다
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class _ZonedFormatter(logging.Formatter):
    """시각을 시간대가 붙은 ISO 형식으로 찍는다 (예: 2026-10-29T16:57:59+09:00)."""

    def __init__(self, fmt: str, offset_hours: int) -> None:
        super().__init__(fmt)
        self._tz = timezone(timedelta(hours=offset_hours))

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return datetime.fromtimestamp(record.created, tz=self._tz).isoformat(timespec="seconds")


class RequestIdFilter(logging.Filter):
    """모든 로그 레코드에 현재 요청의 request_id 를 붙인다."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)

    formatter = _ZonedFormatter(_FORMAT, settings.LOG_UTC_OFFSET_HOURS)
    request_id_filter = RequestIdFilter()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(request_id_filter)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(request_id_filter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(stream_handler)
    root.addHandler(file_handler)
    root.setLevel(settings.LOG_LEVEL.upper())

    # 요청 로그는 우리가 미들웨어에서 직접 남긴다
    logging.getLogger("uvicorn.access").disabled = True
