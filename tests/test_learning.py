"""학습 기록: 세션 목록·상세, 교정 모음, 통계. 남의 기록이 섞이지 않는가."""

from app.db.models import ChatLog, RoleplaySession
from tests.conftest import make_user


def seed(db, user, scenario="cafe", corrections=("fix", None)):
    session = RoleplaySession(user_id=user.id, scenario=scenario)
    db.add(session)
    db.commit()
    for i, correction in enumerate(corrections):
        db.add(ChatLog(user_id=user.id, session_id=session.id, question=f"q{i}",
                       answer=f"a{i}", correction=correction))
    db.commit()
    return session


def test_requires_login(client):
    for path in ("/api/sessions", "/api/corrections", "/api/stats"):
        assert client.get(path).json()["error"] == "UNAUTHORIZED"


def test_session_list_counts_and_detail(auth_client, db_session, user):
    session = seed(db_session, user, corrections=("fix", None, "fix"))
    db_session.add(RoleplaySession(user_id=user.id, scenario="airport"))  # 대화 없는 세션
    db_session.commit()

    rows = auth_client.get("/api/sessions").json()
    assert [(r["scenario"], r["turn_count"], r["correction_count"]) for r in rows] == [
        ("airport", 0, 0), ("cafe", 3, 2),
    ]
    assert rows[1]["last_message_at"].endswith(("Z", "+00:00"))  # 시간대가 없으면 9시간 어긋난다

    detail = auth_client.get(f"/api/sessions/{session.id}").json()
    assert [t["question"] for t in detail["turns"]] == ["q0", "q1", "q2"]


def test_corrections_and_stats(auth_client, db_session, user):
    seed(db_session, user, "cafe", ("fix1", None))
    seed(db_session, user, "airport", ("fix2", "fix3"))

    items = auth_client.get("/api/corrections").json()
    assert [(i["scenario"], i["question"]) for i in items] == [
        ("airport", "q1"), ("airport", "q0"), ("cafe", "q0"),
    ]
    assert len(auth_client.get("/api/corrections?scenario=cafe").json()) == 1

    stats = auth_client.get("/api/stats").json()
    assert stats == {
        "total_sessions": 2, "total_turns": 4, "total_corrections": 3,
        "corrections_by_scenario": {"airport": 2, "cafe": 1},
    }


def test_other_users_records_never_appear(auth_client, db_session, user):
    seed(db_session, make_user(db_session, "other"), "airport")
    seed(db_session, user, "cafe")

    assert [r["scenario"] for r in auth_client.get("/api/sessions").json()] == ["cafe"]
    assert {i["scenario"] for i in auth_client.get("/api/corrections").json()} == {"cafe"}
    assert auth_client.get("/api/stats").json()["total_sessions"] == 1
