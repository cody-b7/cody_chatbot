"""세션과 대화: 시작 → 말하기 → AI 호출 → 저장, 문맥 유지, 입력 검증, AI 실패 처리, 소유권."""

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

from app.core.config import settings
from app.db.models import ChatLog, RoleplaySession
from app.services import ai_client, chat
from app.services.prompt import build_prompt_messages
from tests.conftest import make_user

_REQ = httpx.Request("POST", "https://example.invalid/v1/chat/completions")
TIMEOUT = APITimeoutError(request=_REQ)
CONNECTION = APIConnectionError(request=_REQ)
RATE_LIMITED = APIStatusError("429", response=httpx.Response(429, request=_REQ), body=None)
OK = '{"reply": "ok", "correction": null}'


def start(client, scenario="cafe") -> int:
    return client.post("/api/sessions", json={"scenario": scenario}).json()["id"]


def say(client, session_id, message="I want coffee"):
    return client.post(f"/api/sessions/{session_id}/messages", json={"message": message})


# ---------- 정상 흐름 ----------

def test_requires_login(client):
    assert client.post("/api/sessions", json={"scenario": "cafe"}).status_code == 401
    assert say(client, 1).status_code == 401


def test_message_is_answered_and_saved(auth_client, db_session, user):
    session_id = start(auth_client)
    res = say(auth_client, session_id)

    assert res.status_code == 201
    body = res.json()
    assert body["reply"] and body["correction"] and body["saved"] is True
    log = db_session.query(ChatLog).one()
    assert (log.user_id, log.question, log.answer) == (user.id, "I want coffee", body["reply"])


def test_previous_turns_are_sent_as_context(auth_client, db_session):
    session_id = start(auth_client)
    say(auth_client, session_id, "Hello there")
    history = db_session.query(ChatLog).all()

    messages = build_prompt_messages("cafe", history, "next")
    assert messages[0]["role"] == "system" and "barista" in messages[0]["content"]
    assert [m["content"] for m in messages[1:]] == ["Hello there", history[0].answer, "next"]


def test_db_save_failure_still_returns_reply(auth_client, monkeypatch):
    monkeypatch.setattr(chat, "_save", lambda db, log: False)
    res = say(auth_client, start(auth_client))
    assert res.status_code == 201
    assert res.json()["saved"] is False


# ---------- 입력 검증 ----------

@pytest.mark.parametrize("message", ["   ", chr(0) + chr(1), "a" * 1001])
def test_invalid_message_is_rejected_and_not_saved(auth_client, db_session, message):
    res = say(auth_client, start(auth_client), message)
    assert res.status_code == 422
    assert res.json()["error"] == "INVALID_INPUT"
    assert db_session.query(ChatLog).count() == 0


def test_control_characters_are_removed(auth_client, db_session):
    say(auth_client, start(auth_client), "hi" + chr(0) + " there")
    assert db_session.query(ChatLog).one().question == "hi there"


def test_unknown_scenario_is_rejected(auth_client):
    res = auth_client.post("/api/sessions", json={"scenario": "moon"})
    assert res.status_code == 422
    assert "지원하지 않는 상황" in res.json()["message"]


# ---------- 소유권 ----------

def test_other_users_session_is_forbidden(auth_client, db_session):
    other = make_user(db_session, "other")
    theirs = RoleplaySession(user_id=other.id, scenario="cafe")
    db_session.add(theirs)
    db_session.commit()

    assert say(auth_client, theirs.id).status_code == 403
    assert auth_client.get(f"/api/sessions/{theirs.id}").status_code == 403
    assert say(auth_client, 999999).status_code == 404


# ---------- AI 실패 ----------

@pytest.fixture
def live_ai(monkeypatch):
    monkeypatch.setattr(settings, "AI_MOCK", False)
    monkeypatch.setattr(settings, "AI_FALLBACK_MODEL", "backup-model")


def test_timeout_returns_504_without_fallback(auth_client, db_session, live_ai, ai_outcomes):
    calls = ai_outcomes(TIMEOUT)
    res = say(auth_client, start(auth_client))

    assert res.status_code == 504
    assert res.json()["error"] == "AI_TIMEOUT"
    assert len(calls) == 1  # 이미 기다린 사용자를 또 기다리게 하지 않는다
    assert db_session.query(ChatLog).one().error_code == "AI_TIMEOUT"  # 실패도 기록


@pytest.mark.parametrize("error", [CONNECTION, RATE_LIMITED], ids=["connection", "429"])
def test_provider_error_falls_back_once(auth_client, live_ai, ai_outcomes, error):
    calls = ai_outcomes(error, OK)
    res = say(auth_client, start(auth_client))
    assert res.status_code == 201 and res.json()["reply"] == "ok"
    assert calls == [settings.AI_MODEL, "backup-model"]


def test_both_models_failing_returns_503_with_retry_after(auth_client, live_ai, ai_outcomes):
    ai_outcomes(CONNECTION, CONNECTION)
    res = say(auth_client, start(auth_client))
    assert res.status_code == 503
    assert res.headers["retry-after"]
    assert res.json()["error"] == "AI_ERROR"


def test_failed_turn_is_left_out_of_context(auth_client, db_session, live_ai, ai_outcomes):
    ai_outcomes(TIMEOUT, OK)
    session_id = start(auth_client)
    say(auth_client, session_id, "lost")
    say(auth_client, session_id, "kept")
    assert [t["question"] for t in auth_client.get(f"/api/sessions/{session_id}").json()["turns"]] == ["kept"]


@pytest.mark.parametrize("raw, expected", [
    ('{"reply": "Hi!", "correction": "고칠 것"}', ("Hi!", "고칠 것")),
    ('```json{"reply": "Hi!", "correction": null}```', ("Hi!", None)),
    ("Sure, what size?", ("Sure, what size?", None)),  # 형식을 어겨도 대화는 이어진다
    ('{"reply": "Hi!", "correction": {"a": 1}}', ("Hi!", None)),  # 문자열이 아닌 교정은 버린다
    ('{"reply": "Hi!", "correction": ["x"]}', ("Hi!", None)),
    ('{"reply": "Hi!", "correction": "  "}', ("Hi!", None)),
    ('{"correction": "x"}', ("", "x")),  # reply 가 없으면 빈 대사 (JSON 원문이 새지 않게)
    ('{"reply": null}', ("", None)),
])
def test_reply_parsing(raw, expected):
    assert ai_client._split_reply(raw) == expected


@pytest.mark.parametrize("raw", [
    '{"reply": "", "correction": "x"}', '{"correction": "x"}', '{"reply": null}', '{"reply": 3}',
])
def test_missing_or_empty_reply_returns_503(auth_client, live_ai, ai_outcomes, raw):
    ai_outcomes(raw)
    res = say(auth_client, start(auth_client))
    assert res.status_code == 503
    assert res.headers["retry-after"] and res.json()["error"] == "AI_ERROR"


def test_non_string_correction_is_dropped(auth_client, db_session, live_ai, ai_outcomes):
    ai_outcomes('{"reply": "Sure!", "correction": {"fix": "x"}}')
    res = say(auth_client, start(auth_client))
    assert res.status_code == 201
    assert (res.json()["reply"], res.json()["correction"]) == ("Sure!", None)
    assert db_session.query(ChatLog).one().correction is None


def test_out_of_range_session_id_is_422_not_500(auth_client):
    """SQLite 정수 범위를 넘는 번호가 DB 까지 가면 OverflowError 로 500 이 났다."""
    assert auth_client.get(f"/api/sessions/{10**30}").status_code == 422
    assert say(auth_client, 10**30).status_code == 422


@pytest.mark.parametrize("body, message", [
    ({}, "'message' 값을 확인해 주세요."),
    ({"message": 123}, "'message' 값을 확인해 주세요."),
])
def test_malformed_request_gets_korean_message(auth_client, body, message):
    res = auth_client.post(f"/api/sessions/{start(auth_client)}/messages", json=body)
    assert res.json() == {"error": "INVALID_INPUT", "message": message}


def test_broken_json_gets_korean_message(auth_client):
    res = auth_client.post(f"/api/sessions/{start(auth_client)}/messages", content="{oops",
                           headers={"Content-Type": "application/json"})
    assert res.json()["message"] == "요청 형식을 확인해 주세요."
