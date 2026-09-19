"""화면 라우트 테스트.

기록 화면은 로그인한 사용자만 볼 수 있어야 한다.
비로그인은 401 대신 /login 으로 보낸다 — 화면 요청에 JSON 오류를 주면
사용자에게 보여줄 것이 없기 때문이다.
"""


def test_history_redirects_when_logged_out(client):
    res = client.get("/history", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/login"


def test_history_renders_for_logged_in_user(auth_client, user):
    res = auth_client.get("/history")
    assert res.status_code == 200
    assert user.username in res.text
    # 데이터는 /api/me/* 를 호출해 채운다
    assert "/api/me/sessions" in res.text
    assert "/api/me/stats" in res.text
