"""기록 조회 API 테스트.

핵심은 두 가지다.
  - 집계가 정확한가 (턴 수·교정 수·평균 응답시간)
  - 남의 기록이 절대 섞이지 않는가
"""

from app.models import ChatLog, RoleplaySession, User


def _seed(db, user, scenario="cafe", turns=2, with_correction=1, latency=100):
    session = RoleplaySession(user_id=user.id, scenario=scenario)
    db.add(session)
    db.commit()
    db.refresh(session)
    for i in range(turns):
        db.add(
            ChatLog(
                user_id=user.id,
                session_id=session.id,
                question=f"q{i}",
                answer=f"a{i}",
                correction="고칠 표현" if i < with_correction else None,
                latency_ms=latency,
            )
        )
    db.commit()
    return session


def test_sessions_requires_login(client):
    assert client.get("/api/me/sessions").status_code == 401


def test_stats_requires_login(client):
    assert client.get("/api/me/stats").status_code == 401


def test_session_summary_counts(auth_client, db_session, user):
    _seed(db_session, user, scenario="cafe", turns=3, with_correction=2)

    res = auth_client.get("/api/me/sessions")
    assert res.status_code == 200

    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["scenario"] == "cafe"
    assert rows[0]["turn_count"] == 3
    assert rows[0]["correction_count"] == 2
    assert rows[0]["last_message_at"] is not None


def test_empty_session_counts_zero(auth_client, db_session, user):
    """대화를 한 번도 안 한 세션도 목록에 나와야 한다."""
    db_session.add(RoleplaySession(user_id=user.id, scenario="airport"))
    db_session.commit()

    rows = auth_client.get("/api/me/sessions").json()
    assert rows[0]["turn_count"] == 0
    assert rows[0]["correction_count"] == 0
    assert rows[0]["last_message_at"] is None


def test_sessions_exclude_other_users(auth_client, db_session, user):
    other = User(username="other", password_hash="x")
    db_session.add(other)
    db_session.commit()
    _seed(db_session, other, scenario="airport")
    _seed(db_session, user, scenario="cafe")

    scenarios = [r["scenario"] for r in auth_client.get("/api/me/sessions").json()]
    assert scenarios == ["cafe"]


def test_stats_aggregates(auth_client, db_session, user):
    _seed(db_session, user, turns=2, with_correction=1, latency=100)
    _seed(db_session, user, turns=2, with_correction=2, latency=300)

    stats = auth_client.get("/api/me/stats").json()
    assert stats["total_sessions"] == 2
    assert stats["total_turns"] == 4
    assert stats["total_corrections"] == 3
    assert stats["error_count"] == 0
    assert stats["avg_latency_ms"] == 200


def test_stats_empty_user(auth_client):
    stats = auth_client.get("/api/me/stats").json()
    assert stats["total_sessions"] == 0
    assert stats["total_turns"] == 0
    assert stats["avg_latency_ms"] is None


def test_chats_offset_paging(auth_client, db_session, user):
    _seed(db_session, user, turns=5, with_correction=0)

    first = auth_client.get("/api/me/chats?limit=2").json()
    second = auth_client.get("/api/me/chats?limit=2&offset=2").json()

    assert len(first) == 2 and len(second) == 2
    assert {r["id"] for r in first}.isdisjoint({r["id"] for r in second})
