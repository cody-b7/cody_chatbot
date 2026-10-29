"""화면 라우트 테스트.

로그인이 필요한 화면은 모두 get_current_user 로 막는다.
브라우저(Accept: text/html)로 들어온 비로그인 요청은 401 대신 /login 으로
보내고, fetch·API 클라이언트는 그대로 401 JSON 을 받는다.
"""

import pytest

from app.db import get_db
from app.main import app
from app.models import User
from app.security import hash_password


@pytest.mark.parametrize("path", ["/", "/history", "/corrections"])
def test_pages_redirect_browser_when_logged_out(client, path):
    res = client.get(path, headers={"Accept": "text/html"}, follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/login"


def test_api_still_returns_401_for_fetch(client):
    """화면용 리다이렉트가 API 응답까지 바꿔서는 안 된다."""
    res = client.get("/api/me/sessions", headers={"Accept": "*/*"})
    assert res.status_code == 401
    assert res.json() == {"error": "UNAUTHORIZED", "message": "로그인이 필요합니다."}


def test_history_renders_for_logged_in_user(auth_client, user):
    res = auth_client.get("/history")
    assert res.status_code == 200
    assert user.username in res.text
    assert "/api/me/sessions" in res.text
    assert "/api/me/stats" in res.text


def test_practice_page_renders_for_logged_in_user(auth_client):
    res = auth_client.get("/")
    assert res.status_code == 200
    assert "상황 고르기" in res.text


def test_stale_session_cookie_can_reach_login_again(db_session):
    """계정이 사라진 쿠키로 들어와도 로그인 화면으로 빠져나올 수 있어야 한다.

    예전에는 / 가 세션 값만 보고 화면을 열고, /login 은 세션이 있으니 / 로 보내서
    사용자가 갇혔다.
    """
    from fastapi.testclient import TestClient

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        ghost = User(username="ghost", password_hash=hash_password("goodpass1"))
        db_session.add(ghost)
        db_session.commit()
        client.post("/login", data={"username": "ghost", "password": "goodpass1"})

        db_session.delete(ghost)
        db_session.commit()

        html = {"Accept": "text/html"}
        first = client.get("/", headers=html, follow_redirects=False)
        assert first.headers["location"] == "/login"

        login = client.get("/login", headers=html, follow_redirects=False)
        assert login.status_code == 200, "세션이 비워지지 않아 /login 이 다시 / 로 보냈다"
    finally:
        app.dependency_overrides.clear()


def test_pages_are_hidden_from_api_docs(client):
    paths = client.get("/openapi.json").json()["paths"]
    for page in ("/", "/history", "/corrections", "/login", "/signup"):
        assert "get" not in paths.get(page, {}), f"{page} 화면이 API 문서에 나온다"
    assert "/api/chat" in paths


def test_every_response_has_request_id(client):
    res = client.get("/health")
    assert len(res.headers["x-request-id"]) == 12


def test_request_log_has_user_id(db_session, caplog):
    """요청 로그에 누가 보낸 요청인지 남아야 추적이 된다 (미들웨어 순서 회귀 방지)."""
    import logging

    from fastapi.testclient import TestClient

    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        member = User(username="logged", password_hash=hash_password("goodpass1"))
        db_session.add(member)
        db_session.commit()
        client.post("/login", data={"username": "logged", "password": "goodpass1"})

        caplog.set_level(logging.INFO, logger="cody.request")
        client.get("/health")
        received = [r.getMessage() for r in caplog.records if "request_received" in r.getMessage()]
        assert f"user_id={member.id} " in received[-1]
    finally:
        app.dependency_overrides.clear()
