"""Jinja2 템플릿과 빌드 번호.

빌드 번호(배포된 커밋 해시)는 두 곳에 쓴다.
- CSS 주소에 ?v=<빌드> 를 붙여, 배포 후 브라우저가 이전 CSS 캐시를 쓰지 않게 한다.
- 화면과 응답 헤더 X-App-Build 에 넣어, 배포 전에 열어 둔 화면이면 새로고침을 안내한다.
"""

import subprocess
import time

from fastapi.templating import Jinja2Templates


def _detect_build_id() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=2
        )
        return out.stdout.strip() or str(int(time.time()))
    except (OSError, subprocess.SubprocessError):
        return str(int(time.time()))


BUILD_ID = _detect_build_id()
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["build_id"] = BUILD_ID
