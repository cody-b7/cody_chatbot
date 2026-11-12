"""오류 형식과 핸들러.

모든 오류 응답은 {"error": <코드>, "message": <안내 문구>} 한 가지 형식이다.
서비스 계층은 HTTP 를 몰라도 되도록 AppError 만 던지고, 상태코드로 바꾸는 일은 여기서 한다.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import Event

logger = logging.getLogger("cody.request")


class AppError(Exception):
    """사용자에게 보여줄 수 있는 실패. 상태코드·오류 코드·안내 문구를 함께 가진다."""

    def __init__(
        self, status_code: int, code: str, message: str, headers: dict | None = None
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


def _respond(request: Request, status_code: int, code: str, message: str, headers=None):
    # 주소창으로 연 화면에서 로그인이 풀렸으면 JSON 대신 로그인 화면으로 보낸다
    if status_code == 401 and "text/html" in request.headers.get("accept", ""):
        return RedirectResponse("/login", status_code=303)
    return JSONResponse(
        status_code=status_code, content={"error": code, "message": message}, headers=headers
    )


async def _app_error(request: Request, exc: AppError):
    return _respond(request, exc.status_code, exc.code, exc.message, exc.headers)


_HTTP_MESSAGES = {404: "요청한 주소를 찾을 수 없습니다.", 405: "허용되지 않는 요청 방식입니다."}


async def _http_error(request: Request, exc: StarletteHTTPException):
    # 프레임워크가 내는 404(없는 경로)·405(잘못된 메서드)
    message = _HTTP_MESSAGES.get(exc.status_code, str(exc.detail))
    return _respond(request, exc.status_code, f"HTTP_{exc.status_code}", message)


async def _validation_error(request: Request, exc: RequestValidationError):
    err = (exc.errors() or [{}])[0]
    if err.get("type") == "value_error":  # 스키마 검증기가 직접 쓴 한국어 안내
        message = str(err["msg"]).removeprefix("Value error, ")
    else:  # 필드 누락, 타입 오류, JSON 형식 오류 등 프레임워크의 영어 문구는 감춘다
        field = next((p for p in err.get("loc", ())[1:] if isinstance(p, str)), None)
        message = f"'{field}' 값을 확인해 주세요." if field else "요청 형식을 확인해 주세요."
    return _respond(request, 422, "INVALID_INPUT", message)


async def _unhandled_error(request: Request, exc: Exception):
    logger.exception("%s path=%s", Event.UNHANDLED_ERROR, request.url.path)
    return _respond(request, 500, "INTERNAL_ERROR", "일시적인 오류가 발생했어요.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error)
    app.add_exception_handler(StarletteHTTPException, _http_error)
    app.add_exception_handler(RequestValidationError, _validation_error)
    app.add_exception_handler(Exception, _unhandled_error)
