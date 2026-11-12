"""AI 게이트웨이 호출 (코디세이 공개 API, OpenAI 호환). 키는 서버에만 있다.

정책
  Timeout  : AI_TIMEOUT 초. 넘으면 폴백 없이 바로 504 안내 (대기를 두 배로 늘리지 않는다)
  Retry    : SDK 자동 재시도 끔 (켜 두면 타임아웃도 한 번 더 기다린다)
  Fallback : 429·5xx·연결 실패면 보조 모델로 1회. 그것도 실패하면 503 + Retry-After
"""

import json
import logging
import time
from typing import NamedTuple

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import Event

logger = logging.getLogger("cody.ai")

_client = OpenAI(
    api_key=settings.AI_API_KEY,
    base_url=settings.AI_BASE_URL,  # ".../v1" 까지만 (SDK 가 /chat/completions 를 붙인다)
    timeout=settings.AI_TIMEOUT,
    max_retries=0,
)
_MOCK_REPLY = json.dumps(
    {
        "reply": "Sure! What size would you like?",
        "correction": '"I want coffee" 보다 "Could I get a coffee?" 가 더 자연스러워요.',
    },
    ensure_ascii=False,
)


class AIReply(NamedTuple):
    reply: str  # 상대역의 대사
    correction: str | None  # 한국어 교정 (자연스러웠으면 None)
    latency_ms: int


def ai_timeout() -> AppError:
    return AppError(504, "AI_TIMEOUT", "현재 응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요.")


def ai_unavailable() -> AppError:
    return AppError(
        503, "AI_ERROR", "AI 응답을 받지 못했어요. 잠시 후 다시 시도해 주세요.",
        headers={"Retry-After": "5"},
    )


def generate_ai_reply(messages: list[dict[str, str]]) -> AIReply:
    """대화 문맥을 받아 AI 의 응답(상대역 대사 + 교정)을 생성한다. 실패하면 AppError."""
    started = time.perf_counter()
    logger.info("%s model=%s turns=%d", Event.AI_CALL_START, settings.AI_MODEL, len(messages))

    raw = _complete_with_fallback(messages)
    reply, correction = _split_reply(raw)
    if not reply:
        logger.warning("%s code=AI_ERROR reason=empty_reply", Event.AI_CALL_FAILED)
        raise ai_unavailable()

    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info("%s latency_ms=%d", Event.AI_CALL_SUCCESS, latency_ms)
    return AIReply(reply, correction, latency_ms)


def _complete_with_fallback(messages: list[dict[str, str]]) -> str:
    try:
        return _complete(settings.AI_MODEL, messages)
    except APITimeoutError as exc:
        logger.warning("%s code=AI_TIMEOUT model=%s", Event.AI_CALL_FAILED, settings.AI_MODEL)
        raise ai_timeout() from exc
    except (APIConnectionError, APIStatusError) as exc:  # 429·5xx·연결 실패
        _log_failure(settings.AI_MODEL, exc)
        if not settings.AI_FALLBACK_MODEL:
            raise ai_unavailable() from exc
    except Exception as exc:  # 예상 못 한 오류도 안내 응답으로 바꾼다
        logger.exception("%s code=AI_ERROR reason=unexpected", Event.AI_CALL_FAILED)
        raise ai_unavailable() from exc

    logger.info("%s model=%s", Event.AI_FALLBACK_START, settings.AI_FALLBACK_MODEL)
    try:
        return _complete(settings.AI_FALLBACK_MODEL, messages)
    except Exception as exc:
        _log_failure(settings.AI_FALLBACK_MODEL, exc)
        raise ai_unavailable() from exc


def _log_failure(model: str, exc: Exception) -> None:
    logger.warning("%s code=AI_ERROR model=%s detail=%s", Event.AI_CALL_FAILED, model, exc)


def _complete(model: str, messages: list[dict[str, str]]) -> str:
    """한 모델에 1회 요청하고 응답 원문을 돌려준다."""
    if settings.AI_MOCK:  # 토큰을 쓰지 않는 개발·테스트용
        return _MOCK_REPLY
    options = {}
    if not model.startswith("gpt-5"):  # gpt-5 계열은 temperature 를 보내면 게이트웨이가 거부한다
        options["temperature"] = settings.AI_TEMPERATURE
    resp = _client.chat.completions.create(model=model, messages=messages, **options)
    return (resp.choices[0].message.content or "").strip()


def _split_reply(raw: str) -> tuple[str, str | None]:
    """{"reply", "correction"} JSON 에서 대사와 교정을 꺼낸다.

    게이트웨이가 JSON 전용 모드(response_format)를 지원하지 않아서, 모델이 형식을
    어기면 원문 전체를 대사로 쓴다. 대화는 끊기지 않고 교정만 빠진다.
    """
    try:
        data = json.loads(raw.removeprefix("```json").removesuffix("```"))
        return str(data["reply"]).strip(), data.get("correction") or None
    except (ValueError, KeyError, TypeError, AttributeError):
        return raw, None
