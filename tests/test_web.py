"""화면 라우트, 공통 응답 헤더, 오류 형식, 요청 로그."""

import logging

import pytest

from app.api.templating import BUILD_ID
from app.core.security import hash_password
from app.db.models import User
from tests.conftest import make_user

HTML = {"Accept": "text/html"}


@pytest.mark.parametrize("path", ["/", "/history", "/corrections"])
def test_pages_send_logged_out_browser_to_login(client, path):
    res = client.get(path, headers=HTML, follow_redirects=False)
    assert (res.status_code, res.headers["location"]) == (303, "/login")


def test_api_keeps_json_401_for_fetch(client):
    assert client.get("/api/sessions").json() == {
        "error": "UNAUTHORIZED", "message": "로그인이 필요합니다.",
    }


def test_pages_render_for_logged_in_user(auth_client, user):
    assert "상황 고르기" in auth_client.get("/").text
    history = auth_client.get("/history").text
    assert user.username in history
    assert f"/static/style.css?v={BUILD_ID}" in history  # 배포 후 이전 CSS 캐시를 쓰지 않게


def test_every_response_carries_request_id_and_build(client):
    res = client.get("/health")
    assert len(res.headers["x-request-id"]) == 12
    assert res.headers["x-app-build"] == BUILD_ID


def test_unknown_path_uses_common_error_format(client):
    assert client.get("/api/nothing").json() == {
        "error": "HTTP_404", "message": "요청한 주소를 찾을 수 없습니다.",
    }


def test_api_docs_list_only_apis(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/sessions/{session_id}/messages" in paths
    assert not {"/", "/history", "/corrections"} & paths.keys()


def test_stale_cookie_can_reach_login_again(client, db_session):
    """계정이 사라진 쿠키로 들어와도 로그인 화면으로 빠져나올 수 있어야 한다."""
    ghost = make_user(db_session, "ghost", hash_password("goodpass1"))
    client.post("/login", data={"username": "ghost", "password": "goodpass1"})
    db_session.delete(ghost)
    db_session.commit()

    assert client.get("/", headers=HTML, follow_redirects=False).headers["location"] == "/login"
    assert client.get("/login", headers=HTML, follow_redirects=False).status_code == 200


def test_request_log_has_user_id(client, db_session, caplog):
    """세션 미들웨어가 먼저 실행돼야 요청 로그에 누가 보냈는지 남는다."""
    member: User = make_user(db_session, "logged", hash_password("goodpass1"))
    client.post("/login", data={"username": "logged", "password": "goodpass1"})
    caplog.set_level(logging.INFO, logger="cody.request")

    client.get("/health")
    received = [r.getMessage() for r in caplog.records if "request_received" in r.getMessage()]
    assert f"user_id={member.id} " in received[-1]
