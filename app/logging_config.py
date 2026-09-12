"""로깅 설정.

요건상 남아야 하는 이벤트:
  request_received / ai_call_start / ai_call_success / ai_call_failed
  / db_save_success / db_save_failed

TODO(A): 배포 시 파일 핸들러(RotatingFileHandler)를 추가할 것.
"""

import logging
import sys

from app.config import settings

_FORMAT = "%(levelname)-5s %(asctime)s %(name)s %(message)s"


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S"))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.LOG_LEVEL.upper())

    # 요청 로그는 우리가 미들웨어에서 직접 남긴다
    logging.getLogger("uvicorn.access").disabled = True
