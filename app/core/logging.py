"""로깅 설정과 이벤트 이름.

한 줄 형식:
  LEVEL 시각(+09:00) 로거 request_id=<id> <이벤트> key=value ...

- 로거는 분야별로 나눈다: cody.request / cody.auth / cody.ai / cody.db / cody.app
- request_id 는 요청 미들웨어가 contextvar 에 넣고, 필터가 모든 줄에 붙인다.
  요청 → AI 호출 → DB 저장을 한 id 로 묶어 볼 수 있다.
- 파일(logs/app.log, 5MB × 6개)과 표준출력(systemd journal)에 함께 남긴다.

레벨 기준: INFO 정상 흐름 / WARNING 회복 가능한 실패 / ERROR 예상 밖 오류(스택 포함)
"""

import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings

LOG_FILE = Path("logs/app.log")
_FORMAT = "%(levelname)-5s %(asctime)s %(name)s request_id=%(request_id)s %(message)s"

# 요청 밖(앱 시작, 스크립트)에서 찍히는 로그는 "-" 로 남는다
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class Event(StrEnum):
    APP_STARTED = "app_started"
    APP_STOPPED = "app_stopped"
    REQUEST_RECEIVED = "request_received"
    REQUEST_DONE = "request_done"
    UNHANDLED_ERROR = "unhandled_error"
    SIGNUP_SUCCESS = "signup_success"
    SIGNUP_FAILED = "signup_failed"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    STALE_SESSION = "stale_session_cleared"
    AI_CALL_START = "ai_call_start"
    AI_CALL_SUCCESS = "ai_call_success"
    AI_CALL_FAILED = "ai_call_failed"
    AI_FALLBACK_START = "ai_fallback_start"
    DB_SAVE_SUCCESS = "db_save_success"
    DB_SAVE_FAILED = "db_save_failed"


class _ZonedFormatter(logging.Formatter):
    """시각을 시간대가 붙은 ISO 형식으로 찍는다. 서버 시계는 UTC 라 그대로 두면 찾기 어렵다."""

    def __init__(self, offset_hours: int) -> None:
        super().__init__(_FORMAT)
        self._tz = timezone(timedelta(hours=offset_hours))

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return datetime.fromtimestamp(record.created, tz=self._tz).isoformat(timespec="seconds")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def setup_logging() -> None:
    LOG_FILE.parent.mkdir(exist_ok=True)
    handlers = [
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"),
    ]
    formatter = _ZonedFormatter(settings.LOG_UTC_OFFSET_HOURS)
    for handler in handlers:
        handler.setFormatter(formatter)
        handler.addFilter(_RequestIdFilter())

    root = logging.getLogger()
    root.handlers[:] = handlers
    root.setLevel(settings.LOG_LEVEL.upper())
    logging.getLogger("uvicorn.access").disabled = True  # 요청 로그는 미들웨어가 남긴다
