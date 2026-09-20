"""AI 게이트웨이 호출 (코디세이 공개 API, OpenAI 호환).

타임아웃과 실패를 전부 여기서 흡수한다. 라우터는 AIError 하나만 알면 된다.
실제 호출은 서버에서만 일어나며, API 키는 절대 클라이언트로 나가지 않는다.

폴백 정책
  주 모델이 5xx/연결 실패면 보조 모델로 한 번 더 시도한다.
  단 **타임아웃에는 폴백하지 않는다** — 이미 기다린 시간에 또 기다리게 하면
  사용자 체감이 두 배로 나빠지기 때문이다. 타임아웃은 즉시 안내로 돌린다.
"""

import json
import logging
import re
import time
import uuid

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# GPT-5 계열은 기본값(1) 외의 temperature 를 거부한다 (게이트웨이가 502 로 돌려준다).
# 폴백 모델로 쓰려면 이 모델들에는 파라미터를 아예 빼고 보내야 한다.
_FIXED_TEMPERATURE_PREFIXES = ("gpt-5",)

# 모델이 ```json ... ``` 으로 감싸 보내는 경우가 잦아 미리 벗겨낸다
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class AIError(Exception):
    """사용자에게 보여줄 수 있는 형태로 정규화한 AI 호출 실패."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """base_url 은 '.../v1' 까지만 넣는다 (SDK가 /chat/completions 를 붙임)."""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.AI_API_KEY,
            base_url=settings.AI_BASE_URL,
            timeout=settings.AI_TIMEOUT,
            max_retries=1,
        )
    return _client


def _parse(raw: str) -> tuple[str, str | None]:
    """모델이 JSON 규칙을 어겨도 서비스가 죽지 않도록 방어적으로 파싱한다.

    코드펜스를 벗겨 보고, 그래도 JSON이 아니면 응답 전체를 상대역 대사로
    취급하고 교정은 비운다.
    """
    text = raw.strip()
    fenced = _FENCE.match(text)
    if fenced:
        text = fenced.group(1)

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        # 형식을 어겼을 뿐이므로 응답 전체를 대사로 쓴다. 대화는 이어진다.
        logger.warning("ai_response_not_json chars=%d", len(raw))
        return text, None

    if not isinstance(data, dict):
        logger.warning("ai_response_not_object chars=%d", len(raw))
        return text, None

    # JSON 은 맞는데 reply 가 비어 있으면 빈 문자열을 돌려준다.
    # 예전에는 이 경우가 "JSON 이 아님" 으로 떨어져서 JSON 원문이
    # 그대로 챗봇 대사로 화면에 나갔다.
    reply = str(data.get("reply", "")).strip()
    raw_correction = data.get("correction")
    correction = str(raw_correction).strip() if raw_correction else ""
    return reply, correction or None


def _call(model: str, messages: list[dict[str, str]], request_id: str) -> str:
    """한 모델로 1회 호출. 예외는 그대로 올려보낸다."""
    kwargs: dict = {"model": model, "messages": messages}
    if not model.startswith(_FIXED_TEMPERATURE_PREFIXES):
        kwargs["temperature"] = settings.AI_TEMPERATURE

    resp = _get_client().chat.completions.create(**kwargs)
    return (resp.choices[0].message.content or "").strip()


def generate(messages: list[dict[str, str]]) -> tuple[str, str | None, int]:
    """(상대역 응답, 교정, 지연시간ms) 를 돌려준다. 실패 시 AIError."""
    request_id = uuid.uuid4().hex[:8]
    started = time.perf_counter()
    logger.info(
        "ai_call_start request_id=%s model=%s turns=%d mock=%s",
        request_id,
        settings.AI_MODEL,
        len(messages),
        settings.AI_MOCK,
    )

    if settings.AI_MOCK:
        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info("ai_call_success request_id=%s latency_ms=%d mock=True", request_id, latency_ms)
        return (
            "Sure! What size would you like — small, medium, or large?",
            '"I want coffee" 보다 "Could I get a coffee?" 가 더 자연스러워요.',
            latency_ms,
        )

    raw = ""
    try:
        raw = _call(settings.AI_MODEL, messages, request_id)
    except APITimeoutError as exc:
        # 타임아웃은 폴백하지 않는다 — 대기 시간이 두 배가 되므로
        logger.warning("ai_call_failed request_id=%s code=AI_TIMEOUT model=%s", request_id, settings.AI_MODEL)
        raise AIError(
            "AI_TIMEOUT", "현재 응답이 지연되고 있어요. 잠시 후 다시 시도해 주세요."
        ) from exc
    except (APIConnectionError, APIStatusError) as exc:
        logger.warning(
            "ai_call_failed request_id=%s code=AI_ERROR model=%s detail=%s",
            request_id, settings.AI_MODEL, exc,
        )
        if not settings.AI_FALLBACK_MODEL:
            raise AIError(
                "AI_ERROR", "AI 응답을 받지 못했어요. 잠시 후 다시 시도해 주세요."
            ) from exc

        logger.info(
            "ai_fallback_start request_id=%s model=%s", request_id, settings.AI_FALLBACK_MODEL
        )
        try:
            raw = _call(settings.AI_FALLBACK_MODEL, messages, request_id)
        except Exception as fallback_exc:
            logger.warning(
                "ai_call_failed request_id=%s code=AI_ERROR model=%s (fallback) detail=%s",
                request_id, settings.AI_FALLBACK_MODEL, fallback_exc,
            )
            raise AIError(
                "AI_ERROR", "AI 응답을 받지 못했어요. 잠시 후 다시 시도해 주세요."
            ) from fallback_exc
    except Exception as exc:  # 예상 못 한 오류도 서비스를 죽이지 않는다
        logger.exception("ai_call_failed request_id=%s code=AI_ERROR (unexpected)", request_id)
        raise AIError(
            "AI_ERROR", "AI 응답을 받지 못했어요. 잠시 후 다시 시도해 주세요."
        ) from exc

    latency_ms = int((time.perf_counter() - started) * 1000)
    logger.info("ai_call_success request_id=%s latency_ms=%d", request_id, latency_ms)

    if not raw:
        logger.warning("ai_call_failed request_id=%s code=AI_ERROR reason=empty", request_id)
        raise AIError("AI_ERROR", "빈 응답을 받았어요. 다시 시도해 주세요.")

    reply, correction = _parse(raw)
    if not reply:
        logger.warning(
            "ai_call_failed request_id=%s code=AI_ERROR reason=empty_reply", request_id
        )
        raise AIError("AI_ERROR", "빈 응답을 받았어요. 다시 시도해 주세요.")

    return reply, correction, latency_ms
