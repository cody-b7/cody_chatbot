"""앱 진입점.

TODO(A): 테이블 생성을 지금은 create_all 로 처리한다. 스키마가 자주 바뀌면
         Alembic 도입을 검토할 것 (이번 범위에서는 create_all 로 충분).
"""

import logging
import time

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app import models  # noqa: F401  (create_all 이 테이블을 인식하려면 필요)
from app.config import settings
from app.db import Base, engine
from app.logging_config import setup_logging
from app.routers import admin_logs, auth, chat, history, logs, pages

setup_logging()
logger = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Cody Chatbot", description="영어 회화 롤플레이 파트너")

app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    user_id = request.session.get("user_id") if "session" in request.scope else None
    logger.info(
        "request_received user_id=%s method=%s path=%s",
        user_id,
        request.method,
        request.url.path,
    )
    response = await call_next(request)
    logger.info(
        "request_done path=%s status=%s took_ms=%d",
        request.url.path,
        response.status_code,
        int((time.perf_counter() - started) * 1000),
    )
    return response


@app.exception_handler(StarletteHTTPException)
async def auth_redirect(request: Request, exc: StarletteHTTPException):
    """브라우저로 들어온 401 은 로그인 화면으로 보낸다.

    화면 요청에 JSON 오류를 돌려주면 사용자에게 보여줄 것이 없다.
    fetch 나 API 클라이언트는 Accept 에 text/html 을 넣지 않으므로
    기존대로 401 JSON 을 받는다.
    """
    wants_html = "text/html" in request.headers.get("accept", "")
    if exc.status_code == 401 and wants_html:
        return RedirectResponse("/login", status_code=303)
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    """어떤 예외도 서비스를 죽이지 않고 안내 응답으로 바꾼다."""
    logger.exception("unhandled_error path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "message": "일시적인 오류가 발생했어요."},
    )


@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok"}


app.include_router(pages.router)   # B
app.include_router(auth.router)    # B
app.include_router(chat.router)    # C
app.include_router(logs.router)    # C
app.include_router(history.router) # C
app.include_router(admin_logs.router) # A