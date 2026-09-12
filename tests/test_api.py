"""요건별 동작 확인.

  - 접근 제어: 비로그인은 챗봇을 못 쓴다
  - 입력 검증: 빈 입력 / 길이 초과 / 미지원 시나리오
  - 파이프라인: 질문 -> AI 호출 -> DB 저장 -> 응답
  - 문맥 유지: 같은 세션의 직전 대화가 다음 요청에 들어간다
  - 로그 격리: 남의 로그는 보이지 않는다
"""

from app.models import ChatLog, RoleplaySession, User
from app.services import context


def test_health(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_chat_requires_login(client):
    res = client.post("/api/chat", json={"message": "hello", "scenario": "cafe"})
    assert res.status_code == 401


def test_blank_message_rejected(auth_client):
    res = auth_client.post("/api/chat", json={"message": "   ", "scenario": "cafe"})
    assert res.status_code == 422


def test_too_long_message_rejected(auth_client):
    res = auth_client.post("/api/chat", json={"message": "a" * 5000, "scenario": "cafe"})
    assert res.status_code == 422


def test_unknown_scenario_rejected(auth_client):
    res = auth_client.post("/api/chat", json={"message": "hi", "scenario": "moon"})
    assert res.status_code == 422


def test_pipeline_saves_log(auth_client, db_session, user):
    res = auth_client.post("/api/chat", json={"message": "I want coffee", "scenario": "cafe"})
    assert res.status_code == 200

    body = res.json()
    assert body["reply"]
    assert body["session_id"] > 0

    logs = db_session.query(ChatLog).filter(ChatLog.user_id == user.id).all()
    assert len(logs) == 1
    assert logs[0].question == "I want coffee"
    assert logs[0].answer == body["reply"]


def test_context_carries_previous_turn(auth_client, db_session):
    first = auth_client.post("/api/chat", json={"message": "Hello there", "scenario": "cafe"})
    session_id = first.json()["session_id"]

    second = auth_client.post(
        "/api/chat",
        json={"message": "What did I say?", "scenario": "cafe", "session_id": session_id},
    )
    assert second.json()["session_id"] == session_id  # 같은 세션을 이어간다

    session = db_session.get(RoleplaySession, session_id)
    messages = context.build_messages(db_session, session, "next turn")
    assert messages[0]["role"] == "system"
    assert any(m["content"] == "Hello there" for m in messages)


def test_cannot_use_someone_elses_session(auth_client, db_session, user):
    other = User(username="other", password_hash="x")
    db_session.add(other)
    db_session.commit()
    stolen = RoleplaySession(user_id=other.id, scenario="cafe")
    db_session.add(stolen)
    db_session.commit()

    res = auth_client.post(
        "/api/chat",
        json={"message": "hi", "scenario": "cafe", "session_id": stolen.id},
    )
    assert res.status_code == 404


def test_my_chats_returns_only_own_logs(auth_client, db_session, user):
    auth_client.post("/api/chat", json={"message": "mine", "scenario": "cafe"})

    other = User(username="other", password_hash="x")
    db_session.add(other)
    db_session.commit()
    other_session = RoleplaySession(user_id=other.id, scenario="cafe")
    db_session.add(other_session)
    db_session.commit()
    db_session.add(
        ChatLog(
            user_id=other.id,
            session_id=other_session.id,
            question="theirs",
            answer="theirs",
        )
    )
    db_session.commit()

    res = auth_client.get("/api/me/chats")
    assert res.status_code == 200
    questions = [row["question"] for row in res.json()]
    assert questions == ["mine"]
