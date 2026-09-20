"""AI 호출 실패 경로.

요건 5 — "AI API 실패/타임아웃 상황에서 서비스가 비정상 종료되지 않아야 하고,
사용자에게 오류를 알리는 응답이 제공되어야 한다".

정상 경로는 다른 테스트가 덮는다. 여기서는 **실패했을 때 무슨 일이 일어나는지**만 본다.
"""

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

from app.config import settings
from app.models import ChatLog
from app.services import ai
from app.services.ai import AIError

_REQ = httpx.Request("POST", "https://example.invalid/v1/chat/completions")


def _timeout() -> APITimeoutError:
    return APITimeoutError(request=_REQ)


def _connection() -> APIConnectionError:
    return APIConnectionError(request=_REQ)


def _status() -> APIStatusError:
    return APIStatusError(
        "provider error",
        response=httpx.Response(502, request=_REQ),
        body=None,
    )


@pytest.fixture
def live_ai(monkeypatch):
    """mock 분기를 끄고 실제 호출 경로를 타게 한다."""
    monkeypatch.setattr(settings, "AI_MOCK", False)


def _fail_with(monkeypatch, *errors):
    """_call 이 호출될 때마다 errors 를 순서대로 뱉는다. 호출 기록을 돌려준다."""
    calls: list[str] = []
    it = iter(errors)

    def fake(model, messages, request_id):
        calls.append(model)
        outcome = next(it)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(ai, "_call", fake)
    return calls


# ---------- 타임아웃 ----------

def test_timeout_returns_dedicated_code(live_ai, monkeypatch):
    _fail_with(monkeypatch, _timeout())
    with pytest.raises(AIError) as exc:
        ai.generate([{"role": "user", "content": "hi"}])
    assert exc.value.code == "AI_TIMEOUT"
    assert exc.value.message  # 사용자에게 보여줄 문구가 있어야 한다


def test_timeout_does_not_fall_back(live_ai, monkeypatch):
    """이미 기다린 사용자를 또 기다리게 하지 않는다."""
    monkeypatch.setattr(settings, "AI_FALLBACK_MODEL", "backup-model")
    calls = _fail_with(monkeypatch, _timeout())
    with pytest.raises(AIError):
        ai.generate([{"role": "user", "content": "hi"}])
    assert len(calls) == 1, "타임아웃인데 폴백을 시도했다"


# ---------- 폴백 ----------

@pytest.mark.parametrize("error", [_connection(), _status()], ids=["connection", "status"])
def test_falls_back_on_provider_error(live_ai, monkeypatch, error):
    monkeypatch.setattr(settings, "AI_FALLBACK_MODEL", "backup-model")
    calls = _fail_with(monkeypatch, error, '{"reply": "ok", "correction": null}')

    reply, correction, latency = ai.generate([{"role": "user", "content": "hi"}])
    assert reply == "ok"
    assert correction is None
    assert latency >= 0
    assert calls == [settings.AI_MODEL, "backup-model"]


def test_fallback_failure_surfaces_error(live_ai, monkeypatch):
    monkeypatch.setattr(settings, "AI_FALLBACK_MODEL", "backup-model")
    _fail_with(monkeypatch, _connection(), _connection())
    with pytest.raises(AIError) as exc:
        ai.generate([{"role": "user", "content": "hi"}])
    assert exc.value.code == "AI_ERROR"


def test_no_fallback_configured(live_ai, monkeypatch):
    monkeypatch.setattr(settings, "AI_FALLBACK_MODEL", "")
    calls = _fail_with(monkeypatch, _connection())
    with pytest.raises(AIError):
        ai.generate([{"role": "user", "content": "hi"}])
    assert len(calls) == 1


# ---------- 예상 못 한 오류 / 빈 응답 ----------

def test_unexpected_error_is_absorbed(live_ai, monkeypatch):
    """생각지 못한 예외가 그대로 터져나가면 서비스가 500 으로 죽는다."""
    _fail_with(monkeypatch, RuntimeError("뭔가 잘못됨"))
    with pytest.raises(AIError) as exc:
        ai.generate([{"role": "user", "content": "hi"}])
    assert exc.value.code == "AI_ERROR"


def test_empty_response_is_an_error(live_ai, monkeypatch):
    _fail_with(monkeypatch, "")
    with pytest.raises(AIError):
        ai.generate([{"role": "user", "content": "hi"}])


def test_empty_reply_in_valid_json_is_an_error(live_ai, monkeypatch):
    """JSON 은 맞는데 대사가 비어 있는 경우.

    예전에는 이 응답이 "JSON 이 아님" 으로 떨어져서, JSON 원문이 그대로
    챗봇 대사로 화면에 나갔다.
    """
    _fail_with(monkeypatch, '{"reply": "", "correction": "고칠 것"}')
    with pytest.raises(AIError) as exc:
        ai.generate([{"role": "user", "content": "hi"}])
    assert exc.value.code == "AI_ERROR"


# ---------- 응답 파싱 ----------

def test_parses_json():
    assert ai._parse('{"reply": "Hi!", "correction": "고칠 것"}') == ("Hi!", "고칠 것")


def test_null_correction_becomes_none():
    assert ai._parse('{"reply": "Hi!", "correction": null}') == ("Hi!", None)


def test_empty_reply_is_not_mistaken_for_plain_text():
    """JSON 원문이 대사로 새어나가지 않아야 한다."""
    reply, _ = ai._parse('{"reply": "", "correction": "x"}')
    assert reply == ""
    assert "correction" not in reply


def test_non_json_falls_back_to_plain_text():
    """모델이 규칙을 어겨도 대화는 이어져야 한다."""
    reply, correction = ai._parse("Sure, what size?")
    assert reply == "Sure, what size?"
    assert correction is None


# ---------- 라우터: 실패해도 죽지 않고, 기록은 남는다 ----------

def test_chat_returns_503_with_message(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "AI_MOCK", False)
    _fail_with(monkeypatch, _timeout())

    res = auth_client.post("/api/chat", json={"message": "hello", "scenario": "cafe"})
    assert res.status_code == 503  # 500 이 아니다 = 서비스가 죽지 않았다

    body = res.json()
    assert body["error"] == "AI_TIMEOUT"
    assert body["message"], "사용자에게 보여줄 안내가 없다"


def test_failed_turn_is_recorded_for_tracing(auth_client, db_session, user, monkeypatch):
    """실패도 로그로 남아야 원인 추적이 된다."""
    monkeypatch.setattr(settings, "AI_MOCK", False)
    _fail_with(monkeypatch, _timeout())

    auth_client.post("/api/chat", json={"message": "추적될 질문", "scenario": "cafe"})

    log = db_session.query(ChatLog).filter(ChatLog.user_id == user.id).one()
    assert log.error_code == "AI_TIMEOUT"
    assert log.question == "추적될 질문"
    assert log.answer == ""


def test_failed_turn_counts_in_stats(auth_client, monkeypatch):
    monkeypatch.setattr(settings, "AI_MOCK", False)
    _fail_with(monkeypatch, _timeout())
    auth_client.post("/api/chat", json={"message": "hello", "scenario": "cafe"})

    assert auth_client.get("/api/me/stats").json()["error_count"] == 1
