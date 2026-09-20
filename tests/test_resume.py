"""이전 세션 이어하기.

검증 대상
  - 세션 상세가 대화 전체를 순서대로 돌려주는가
  - 남의 세션은 존재조차 알려주지 않는가 (404)
  - 이어쓴 대화가 같은 세션에 쌓이고, 문맥이 유지되는가
  - 이어할 때 상황(scenario)이 세션 값으로 고정되는가
"""

from app.models import ChatLog, RoleplaySession, User
from app.services import context


def test_session_detail_returns_turns_in_order(auth_client, db_session, user):
    s = RoleplaySession(user_id=user.id, scenario="airport")
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    for i in range(3):
        db_session.add(
            ChatLog(user_id=user.id, session_id=s.id, question=f"q{i}", answer=f"a{i}")
        )
    db_session.commit()

    body = auth_client.get(f"/api/me/sessions/{s.id}").json()
    assert body["scenario"] == "airport"
    assert [t["question"] for t in body["turns"]] == ["q0", "q1", "q2"]


def test_session_detail_hides_other_users(auth_client, db_session, user):
    other = User(username="other", password_hash="x")
    db_session.add(other)
    db_session.commit()
    stolen = RoleplaySession(user_id=other.id, scenario="cafe")
    db_session.add(stolen)
    db_session.commit()
    db_session.refresh(stolen)

    assert auth_client.get(f"/api/me/sessions/{stolen.id}").status_code == 404


def test_session_detail_requires_login(client):
    assert client.get("/api/me/sessions/1").status_code == 401


def test_resume_keeps_same_session_and_context(auth_client, db_session):
    first = auth_client.post(
        "/api/chat", json={"message": "I want coffee", "scenario": "cafe"}
    ).json()
    sid = first["session_id"]

    # 화면을 껐다 켜고 이어하기로 돌아온 상황
    detail = auth_client.get(f"/api/me/sessions/{sid}").json()
    assert len(detail["turns"]) == 1

    second = auth_client.post(
        "/api/chat",
        json={"message": "Large please", "scenario": "cafe", "session_id": sid},
    ).json()
    assert second["session_id"] == sid

    session = db_session.get(RoleplaySession, sid)
    messages = context.build_messages(db_session, session, "다음 발화")
    assert any(m["content"] == "I want coffee" for m in messages)


def test_scenario_follows_session_not_request(auth_client):
    """이어할 때 클라이언트가 엉뚱한 상황을 보내도 세션 값이 이긴다."""
    first = auth_client.post(
        "/api/chat", json={"message": "hi", "scenario": "airport"}
    ).json()
    assert first["scenario"] == "airport"

    second = auth_client.post(
        "/api/chat",
        json={"message": "again", "scenario": "cafe", "session_id": first["session_id"]},
    ).json()
    assert second["scenario"] == "airport"


def test_history_page_has_resume_link(auth_client):
    assert "?session=" in auth_client.get("/history").text
