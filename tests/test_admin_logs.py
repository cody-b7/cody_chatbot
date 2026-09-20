"""관리자 운영 로그 조회 API 테스트."""

from app.config import settings
from app.routers import admin_logs


def test_admin_logs_requires_login(client):
    """비로그인 사용자는 접근할 수 없다."""
    response = client.get("/api/admin/logs")

    assert response.status_code == 401


def test_admin_logs_rejects_normal_user(auth_client, monkeypatch):
    """일반 로그인 사용자는 접근할 수 없다."""
    monkeypatch.setattr(settings, "ADMIN_USERNAME", "admin")

    response = auth_client.get("/api/admin/logs")

    assert response.status_code == 403


def test_admin_logs_returns_empty_when_file_missing(
    auth_client,
    monkeypatch,
    tmp_path,
):
    """관리자라도 로그 파일이 없으면 빈 목록을 반환한다."""
    monkeypatch.setattr(settings, "ADMIN_USERNAME", "tester")
    monkeypatch.setattr(
        admin_logs,
        "LOG_FILE",
        tmp_path / "missing.log",
    )

    response = auth_client.get("/api/admin/logs")

    assert response.status_code == 200
    assert response.json() == {"logs": []}


def test_admin_logs_returns_recent_lines(
    auth_client,
    monkeypatch,
    tmp_path,
):
    """관리자는 최근 로그를 조회할 수 있다."""
    monkeypatch.setattr(settings, "ADMIN_USERNAME", "tester")

    log_file = tmp_path / "app.log"
    log_file.write_text(
        "line 1\n"
        "line 2\n"
        "line 3\n"
        "line 4\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(admin_logs, "LOG_FILE", log_file)

    response = auth_client.get("/api/admin/logs?limit=2")

    assert response.status_code == 200
    assert response.json() == {
        "logs": [
            "line 3",
            "line 4",
        ]
    }


def test_admin_logs_limit_validation(
    auth_client,
    monkeypatch,
):
    """limit 허용 범위를 벗어나면 요청을 거부한다."""
    monkeypatch.setattr(settings, "ADMIN_USERNAME", "tester")

    response = auth_client.get("/api/admin/logs?limit=501")

    assert response.status_code == 422