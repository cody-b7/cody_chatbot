"""사용자 입력 검증.

요건 5 — "사용자 입력 검증 로직이 최소 1개 이상 존재해야 한다".
검증은 라우터가 아니라 스키마에서 한다. AI 호출·DB 저장까지 가기 전에
입구에서 막아야 토큰과 저장 공간을 낭비하지 않는다.
"""

import pytest
from pydantic import ValidationError

from app.config import settings
from app.schemas import ChatRequest


@pytest.mark.parametrize(
    "message",
    ["", "   ", "\n\n", "\t"],
    ids=["빈문자", "공백", "줄바꿈만", "탭만"],
)
def test_blank_messages_rejected(message):
    with pytest.raises(ValidationError):
        ChatRequest(message=message)


def test_too_long_message_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(message="a" * (settings.MAX_MESSAGE_LENGTH + 1))


def test_boundary_length_accepted():
    msg = "a" * settings.MAX_MESSAGE_LENGTH
    assert ChatRequest(message=msg).message == msg


def test_surrounding_whitespace_trimmed():
    assert ChatRequest(message="  hello  ").message == "hello"


def test_control_characters_removed():
    """널 바이트가 섞이면 로그가 깨지고 조회 도구마다 다르게 보인다."""
    cleaned = ChatRequest(message="hi" + chr(0) + chr(7) + " there").message
    assert cleaned == "hi there"


def test_newline_and_tab_survive():
    """줄바꿈은 사용자가 의도한 입력일 수 있다."""
    assert ChatRequest(message="a" + chr(10) + "b").message == "a" + chr(10) + "b"


def test_control_only_message_rejected():
    """제어 문자를 걷어내면 빈 문자열이 되는 경우."""
    with pytest.raises(ValidationError):
        ChatRequest(message=chr(0) + chr(1))


@pytest.mark.parametrize("session_id", [0, -1, -999], ids=["0", "-1", "-999"])
def test_non_positive_session_id_rejected(session_id):
    with pytest.raises(ValidationError):
        ChatRequest(message="hi", session_id=session_id)


def test_unknown_scenario_rejected():
    with pytest.raises(ValidationError):
        ChatRequest(message="hi", scenario="moon_base")


def test_known_scenarios_accepted():
    from app.scenarios import KEYS

    for key in KEYS:
        assert ChatRequest(message="hi", scenario=key).scenario == key


# ---------- HTTP 계층에서도 같은 결과가 나오는지 ----------

@pytest.mark.parametrize(
    "payload",
    [
        {"message": "   ", "scenario": "cafe"},
        {"message": "a" * 5000, "scenario": "cafe"},
        {"message": "hi", "scenario": "moon_base"},
        {"message": "hi", "scenario": "cafe", "session_id": 0},
    ],
    ids=["빈입력", "길이초과", "미지원상황", "잘못된세션"],
)
def test_invalid_requests_return_422(auth_client, payload):
    res = auth_client.post("/api/chat", json=payload)
    assert res.status_code == 422


def test_invalid_input_is_not_saved(auth_client, db_session, user):
    """검증에서 막힌 요청은 DB 에 흔적을 남기지 않는다."""
    from app.models import ChatLog

    auth_client.post("/api/chat", json={"message": "   ", "scenario": "cafe"})
    assert db_session.query(ChatLog).filter(ChatLog.user_id == user.id).count() == 0
