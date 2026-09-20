"""테스트 픽스처.

DB는 메모리 SQLite로 갈아끼우고, AI 호출은 항상 mock 으로 고정한다.
(테스트가 실수로 실제 게이트웨이를 부르면 팀 토큰 한도가 깎인다)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.deps import get_current_user
from app.main import app
from app.models import User


@pytest.fixture(autouse=True)
def fixed_settings(monkeypatch):
    """테스트는 항상 CI 와 같은 조건에서 돈다.

    개발용 .env 의 DEV_AUTH_BYPASS=true 가 새어 들어오면 인증이 항상
    통과해버려서, 로컬에서만 초록불인 테스트가 만들어진다.
    """
    monkeypatch.setattr(settings, "AI_MOCK", True)
    monkeypatch.setattr(settings, "DEV_AUTH_BYPASS", False)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def user(db_session) -> User:
    u = User(username="tester", password_hash="x")
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def client(db_session):
    """비로그인 클라이언트."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client(db_session, user):
    """로그인된 클라이언트.

    B가 인증을 완성한 뒤에도 이 오버라이드 덕분에 테스트는 그대로 돈다.
    """
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user
    yield TestClient(app)
    app.dependency_overrides.clear()
