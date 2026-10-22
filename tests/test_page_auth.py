"""화면의 로그인 판정.

세션 값이 아니라 실제 사용자로 판단해야 한다.
계정이 없어진 쿠키로 들어와도 로그인 화면으로 빠져나올 수 있어야 한다.
"""

from app.models import User

HTML = {"Accept": "text/html"}


def _signup(client, username="jinu"):
    client.post("/signup", data={"username": username, "password": "test1234"})


def test_logged_out_user_goes_to_login(client):
    res = client.get("/", headers=HTML, follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/login"


def test_logged_in_user_sees_chat(client, db_session):
    _signup(client)
    res = client.get("/", headers=HTML, follow_redirects=False)
    assert res.status_code == 200


def test_logged_in_user_skips_login_page(client):
    _signup(client)
    for path in ("/login", "/signup"):
        res = client.get(path, follow_redirects=False)
        assert res.status_code == 303
        assert res.headers["location"] == "/"


def test_stale_session_can_reach_login(client, db_session):
    """계정은 지워졌는데 쿠키가 남은 경우 — 예전에는 빠져나올 수 없었다."""
    _signup(client)
    db_session.query(User).delete()
    db_session.commit()

    # 채팅 화면 대신 로그인으로 보낸다
    res = client.get("/", headers=HTML, follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/login"

    # 로그인 화면이 실제로 열린다 (다시 / 로 튕기지 않는다)
    res = client.get("/login", follow_redirects=False)
    assert res.status_code == 200


def test_login_error_message_rendered(client):
    res = client.get("/login?error=bad_credentials")
    assert res.status_code == 200
    assert "올바르지 않습니다" in res.text
