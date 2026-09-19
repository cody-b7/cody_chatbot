"""로깅 설정.

요건상 남아야 하는 이벤트:
  request_received / ai_call_start / ai_call_success / ai_call_failed
  / db_save_success / db_save_failed

TODO(A): 배포 시 파일 핸들러(RotatingFileHandler)를 추가할 것.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import settings

_FORMAT = "%(levelname)-5s %(asctime)s %(name)s %(message)s"

LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "app.log"


def setup_logging() -> None:
    LOG_DIR.mkdir(exist_ok=True)

    formatter = logging.Formatter(
        _FORMAT,
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(stream_handler)
    root.addHandler(file_handler)
    root.setLevel(settings.LOG_LEVEL.upper())

    # 요청 로그는 우리가 미들웨어에서 직접 남긴다
    logging.getLogger("uvicorn.access").disabled = True