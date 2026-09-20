"""교정 조회 API 테스트.

교정만 골라 보여주는 화면의 데이터원이다. 검증 대상은 세 가지.
  - 교정이 달린 턴만 나오는가
  - 어떤 상황에서 틀렸는지(scenario)가 함께 오는가
  - 남의 교정이 섞이지 않는가
"""

from app.models import ChatLog, RoleplaySession, User


def _add(db, user, scenario, question, correction):
    session = db.query(RoleplaySession).filter_by(
        user_id=user.id, scenario=scenario
    ).first()
    if session is None:
        session = RoleplaySession(user_id=user.id, scenario=scenario)
        db.add(session)
        db.commit()
        db.refresh(session)
    db.add(
        ChatLog(
            user_id=user.id,
            session_id=session.id,
            question=question,
            answer="ok",
            correction=correction,
        )
    )
    db.commit()


def test_requires_login(client):
    assert client.get("/api/me/corrections").status_code == 401
    assert client.get("/api/me/corrections/by-scenario").status_code == 401


def test_only_corrected_turns(auth_client, db_session, user):
    _add(db_session, user, "cafe", "I want coffee", "Could I get a coffee?")
    _add(db_session, user, "cafe", "Thanks", None)  # 교정 없는 턴

    items = auth_client.get("/api/me/corrections").json()
    assert len(items) == 1
    assert items[0]["question"] == "I want coffee"
    assert items[0]["scenario"] == "cafe"


def test_filter_by_scenario(auth_client, db_session, user):
    _add(db_session, user, "cafe", "q1", "fix1")
    _add(db_session, user, "airport", "q2", "fix2")

    items = auth_client.get("/api/me/corrections?scenario=airport").json()
    assert [i["question"] for i in items] == ["q2"]


def test_by_scenario_counts(auth_client, db_session, user):
    _add(db_session, user, "cafe", "q1", "fix")
    _add(db_session, user, "cafe", "q2", "fix")
    _add(db_session, user, "airport", "q3", "fix")

    assert auth_client.get("/api/me/corrections/by-scenario").json() == {
        "cafe": 2,
        "airport": 1,
    }


def test_excludes_other_users(auth_client, db_session, user):
    other = User(username="other", password_hash="x")
    db_session.add(other)
    db_session.commit()
    _add(db_session, other, "cafe", "남의 말", "남의 교정")
    _add(db_session, user, "cafe", "내 말", "내 교정")

    items = auth_client.get("/api/me/corrections").json()
    assert [i["question"] for i in items] == ["내 말"]
    assert auth_client.get("/api/me/corrections/by-scenario").json() == {"cafe": 1}


def test_page_renders(auth_client, user):
    res = auth_client.get("/corrections")
    assert res.status_code == 200
    assert user.username in res.text
    assert "/api/me/corrections/by-scenario" in res.text


def test_page_redirects_browser_when_logged_out(client):
    res = client.get(
        "/corrections", headers={"Accept": "text/html"}, follow_redirects=False
    )
    assert res.status_code == 303
    assert res.headers["location"] == "/login"
