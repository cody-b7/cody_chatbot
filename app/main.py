"""앱 진입점: 앱을 만들고 미들웨어·오류 핸들러·라우터를 등록한다.

계층 구조
  api/routes   HTTP 입출력 (요청 검증, 응답 모양)
  services     기능 흐름 (대화, 인증, AI 호출)
  repositories DB 조회·저장
  db / schemas / core  모델, 요청·응답 계약, 설정·로깅·보안 공통
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import admin, auth, learning, pages, sessions
from app.api.templating import BUILD_ID
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging import Event, request_id_var, setup_logging
from app.db.models import Base
from app.db.session import checkpoint_wal, engine

setup_logging()
logger = logging.getLogger("cody.request")
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 시작·종료 때 SQLite WAL 을 본 DB 파일로 옮긴다 (app/db/session.py 참고)
    checkpoint_wal()
    logging.getLogger("cody.app").info("%s", Event.APP_STARTED)
    yield
    checkpoint_wal()
    engine.dispose()
    logging.getLogger("cody.app").info("%s", Event.APP_STOPPED)


app = FastAPI(title="Cody Chatbot", description="영어 회화 롤플레이 파트너", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
register_error_handlers(app)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """요청마다 request_id 를 정하고 들어올 때·나갈 때 한 줄씩 남긴다."""
    request_id = uuid.uuid4().hex[:12]
    request_id_var.set(request_id)  # 이 요청 안의 AI·DB 로그에도 같은 id 가 붙는다
    started = time.perf_counter()
    logger.info(
        "%s user_id=%s method=%s path=%s",
        Event.REQUEST_RECEIVED, request.session.get("user_id"), request.method, request.url.path,
    )
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id  # 오류 신고 때 이 값으로 로그를 찾는다
        response.headers["X-App-Build"] = BUILD_ID  # 화면이 자기 빌드와 비교해 새로고침 안내
        return response
    finally:
        took_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "%s path=%s status=%s took_ms=%d",
            Event.REQUEST_DONE, request.url.path, status_code, took_ms,
        )


# 나중에 등록한 미들웨어가 바깥에서 먼저 실행된다. 세션을 먼저 풀어야 요청 로그에 user_id 가 남는다.
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY)

for module in (pages, auth, sessions, learning, admin):
    app.include_router(module.router)


@app.get("/health", tags=["ops"], summary="서버 상태 확인")
def health():
    return {"status": "ok"}
