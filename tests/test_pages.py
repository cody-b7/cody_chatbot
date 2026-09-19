"""화면 라우트 테스트.

기록 화면은 로그인한 사용자만 볼 수 있다.
브라우저(Accept: text/html)로 들어온 비로그인 요청은 401 대신 /login 으로
보내고, fetch·API 클라이언트는 그대로 401 JSON 을 받는다.
"""


def test_history_redirects_browser_when_logged_out(client):
    res = client.get(
        "/history", headers={"Accept": "text/html"}, follow_redirects=False
    )
    assert res.status_code == 303
    assert res.headers["location"] == "/login"


def test_api_still_returns_401_for_fetch(client):
    """화면용 리다이렉트가 API 응답까지 바꿔서는 안 된다."""
    res = client.get("/api/me/sessions", headers={"Accept": "*/*"})
    assert res.status_code == 401


def test_history_renders_for_logged_in_user(auth_client, user):
    res = auth_client.get("/history")
    assert res.status_code == 200
    assert user.username in res.text
    assert "/api/me/sessions" in res.text
    assert "/api/me/stats" in res.text
