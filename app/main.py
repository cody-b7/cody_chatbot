"""앱 진입점.

TODO(A): 테이블 생성을 지금은 create_all 로 처리한다. 스키마가 자주 바뀌면
         Alembic 도입을 검토할 것 (이번 범위에서는 create_all 로 충분).

오류 응답은 모두 {"error": <코드>, "message": <안내 문구>} 한 가지 형식이다.
화면은 message 만 보여주면 되고, 코드는 로그·통계에서 원인을 가를 때 쓴다.
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app import models  # noqa: F401  (create_all 이 테이블을 인식하려면 필요)
from app.config import settings
from app.db import Base, checkpoint_wal, engine
from app.log_events import Event
from app.logging_config import request_id_var, setup_logging
from app.routers import admin_logs, auth, chat, pages, records
from app.templating import BUILD_ID

setup_logging()
logger = logging.getLogger("cody.request")

Base.metadata.create_all(bind=engine)

app_logger = logging.getLogger("cody.app")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """시작·종료 때 SQLite WAL 을 본 DB 파일로 옮긴다.

    시작할 때: 지난번에 정상 종료되지 못했어도(전원 차단 등) 남은 WAL 을 반영한다.
    종료할 때: systemctl stop/restart 나 배포로 내려갈 때 커밋된 데이터를 본 파일에 확정한다.
    """
    checkpoint_wal()
    app_logger.info("%s", Event.APP_STARTED)
    yield
    checkpoint_wal()
    engine.dispose()
    app_logger.info("%s", Event.APP_STOPPED)


app = FastAPI(
    lifespan=lifespan,
    title="Cody Chatbot",
    description="영어 회화 롤플레이 파트너. 화면 라우트는 문서에서 제외했다.",
    openapi_tags=[
        {"name": "chat", "description": "상대역과 대화 (AI 호출)"},
        {"name": "records", "description": "내 학습 기록 조회. 로그인한 사용자 본인 것만"},
        {"name": "auth", "description": "회원가입·로그인 (HTML 폼 POST)"},
        {"name": "admin", "description": "운영 로그 조회. 관리자만"},
        {"name": "ops", "description": "상태 확인"},
    ],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

# HTTP 상태코드 → 오류 코드 (HTTPException 에는 코드가 없으므로 여기서 붙인다)
_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """요청마다 request_id 를 정하고, 들어올 때와 나갈 때 한 줄씩 남긴다.

    request_id 는 contextvar 에 넣어 두므로 이 요청 안에서 찍히는
    AI 호출·DB 저장 로그에도 같은 id 가 붙는다. 응답 헤더로도 내려주어,
    사용자가 오류를 신고할 때 이 값으로 로그를 바로 찾을 수 있다.
    """
    request_id = uuid.uuid4().hex[:12]
    # reset 하지 않는다: 요청마다 별도 컨텍스트에서 돌고, 바깥의 500 핸들러 로그에도 id 가 남아야 한다
    request_id_var.set(request_id)
    started = time.perf_counter()
    user_id = request.session.get("user_id")
    logger.info(
        "%s user_id=%s method=%s path=%s",
        Event.REQUEST_RECEIVED,
        user_id,
        request.method,
        request.url.path,
    )
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        # 화면이 자기 빌드와 비교해 새로고침 안내를 띄운다 (base.html)
        response.headers["X-App-Build"] = BUILD_ID
        return response
    finally:
        # 처리 중 예외가 나도 request_done 은 남긴다 (status=500)
        logger.info(
            "%s path=%s status=%s took_ms=%d",
            Event.REQUEST_DONE,
            request.url.path,
            status_code,
            int((time.perf_counter() - started) * 1000),
        )


# 세션 미들웨어는 요청 로그 미들웨어보다 나중에 등록한다.
# 나중에 등록한 미들웨어가 바깥에서 먼저 실행되므로, 요청 로그가 찍힐 때
# 세션(user_id)이 이미 채워져 있다. 순서가 반대면 user_id 가 항상 None 으로 남는다.
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    """HTTPException 을 공통 오류 형식으로 바꾼다.

    브라우저로 들어온 401 은 로그인 화면으로 보낸다. 화면 요청에 JSON 오류를
    돌려주면 사용자에게 보여줄 것이 없다. fetch 나 API 클라이언트는 Accept 에
    text/html 을 넣지 않으므로 401 JSON 을 받는다.
    """
    wants_html = "text/html" in request.headers.get("accept", "")
    if exc.status_code == 401 and wants_html:
        return RedirectResponse("/login", status_code=303)

    message = exc.detail if isinstance(exc.detail, str) else "요청을 처리할 수 없어요."
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": _ERROR_CODES.get(exc.status_code, f"HTTP_{exc.status_code}"),
            "message": message,
        },
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    """입력 검증 실패(422)도 같은 형식으로. 첫 번째 위반 사유를 안내 문구로 쓴다."""
    errors = exc.errors()
    message = "보낸 내용을 확인해 주세요."
    if errors:
        # 스키마의 ValueError 문구 앞에 pydantic 이 붙이는 접두어를 떼어 낸다
        message = str(errors[0].get("msg", message)).removeprefix("Value error, ")
    return JSONResponse(
        status_code=422,
        content={"error": "INVALID_INPUT", "message": message},
    )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    """어떤 예외도 서비스를 죽이지 않고 안내 응답으로 바꾼다."""
    logger.exception("%s path=%s", Event.UNHANDLED_ERROR, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "message": "일시적인 오류가 발생했어요."},
    )


@app.get("/health", tags=["ops"], summary="서버 상태 확인")
def health():
    return {"status": "ok"}


app.include_router(pages.router)       # 화면
app.include_router(auth.router)        # 회원가입·로그인
app.include_router(chat.router)        # 대화
app.include_router(records.router)     # 내 학습 기록
app.include_router(admin_logs.router)  # 운영 로그
