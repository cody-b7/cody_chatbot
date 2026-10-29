"""Jinja2 템플릿 공용 객체와 빌드 번호. 화면 라우터와 인증 라우터가 함께 쓴다.

빌드 번호
  배포된 코드의 커밋 해시(없으면 서버 시작 시각)다. 두 곳에 쓴다.
  - 정적 파일 주소에 ?v=<빌드> 를 붙여, 배포 후 브라우저가 옛 CSS 캐시를 쓰지 않게 한다.
  - 화면에 심어 두고 API 응답 헤더(X-App-Build)와 비교해, 배포 전에 열어 둔 화면이면
    새로고침 안내를 띄운다 (base.html).
"""

import subprocess
import time

from fastapi.templating import Jinja2Templates


def _detect_build_id() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        return out.stdout.strip() or str(int(time.time()))
    except (OSError, subprocess.SubprocessError):
        return str(int(time.time()))


BUILD_ID = _detect_build_id()

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["build_id"] = BUILD_ID
