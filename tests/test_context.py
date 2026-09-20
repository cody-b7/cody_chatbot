"""시나리오 정의와 문맥 구성.

정의가 두 곳에 흩어져 있던 시절에는 한쪽에만 상황을 추가하면
검증은 통과하는데 AI 는 엉뚱한 역할을 연기했다. 그 어긋남을 테스트로 막는다.
"""

import pytest

from app import scenarios
from app.config import settings
from app.models import ChatLog, RoleplaySession
from app.schemas import SCENARIOS as SCHEMA_SCENARIOS
from app.services import context


def test_definition_has_single_source():
    """입력 검증에 쓰는 목록과 실제 정의가 같아야 한다."""
    assert tuple(SCHEMA_SCENARIOS) == scenarios.KEYS


@pytest.mark.parametrize("scenario", scenarios.SCENARIOS, ids=lambda s: s.key)
def test_every_scenario_is_complete(scenario):
    assert scenario.label, f"{scenario.key}: 화면에 보여줄 한국어 이름이 없다"
    assert scenario.role.startswith("You are"), f"{scenario.key}: 배역 설명이 없다"
    assert scenario.goal, f"{scenario.key}: 학습 목표가 없다"


def test_unknown_scenario_falls_back():
    """모르는 키가 와도 대화가 끊기지 않는다."""
    assert scenarios.get("moon_base") is scenarios.DEFAULT


def _session(db, user, scenario="hotel"):
    s = RoleplaySession(user_id=user.id, scenario=scenario)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def test_prompt_carries_role_and_goal(db_session, user):
    session = _session(db_session, user, "hotel")
    system = context.build_messages(db_session, session, "hi")[0]["content"]

    hotel = scenarios.get("hotel")
    assert hotel.role in system
    assert hotel.goal in system


def test_prompt_limits_corrections_to_one():
    """교정을 매턴 몰아주면 학습자가 말을 안 하게 된다."""
    assert "AT MOST ONE" in context.SYSTEM_TEMPLATE


def test_only_recent_turns_are_sent(db_session, user, monkeypatch):
    """토큰 한도 때문에 최근 N턴만 넣는다."""
    monkeypatch.setattr(settings, "AI_MAX_CONTEXT_TURNS", 2)
    session = _session(db_session, user)
    for i in range(5):
        db_session.add(
            ChatLog(user_id=user.id, session_id=session.id, question=f"q{i}", answer=f"a{i}")
        )
    db_session.commit()

    contents = [m["content"] for m in context.build_messages(db_session, session, "지금")]
    assert "q4" in contents and "q3" in contents  # 최근 2턴
    assert "q0" not in contents and "q2" not in contents


def test_failed_turns_are_excluded(db_session, user):
    """타임아웃으로 답을 못 받은 턴은 문맥에 넣지 않는다."""
    session = _session(db_session, user)
    db_session.add(
        ChatLog(
            user_id=user.id, session_id=session.id,
            question="실패한 질문", answer="", error_code="AI_TIMEOUT",
        )
    )
    db_session.add(
        ChatLog(user_id=user.id, session_id=session.id, question="정상 질문", answer="ok")
    )
    db_session.commit()

    contents = [m["content"] for m in context.build_messages(db_session, session, "지금")]
    assert "정상 질문" in contents
    assert "실패한 질문" not in contents
