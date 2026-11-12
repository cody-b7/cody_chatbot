"""테스트 픽스처. DB 는 메모리 SQLite, AI 는 항상 mock (실제 게이트웨이를 부르면 팀 토큰이 깎인다)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.models import Base, User
from app.db.session import get_db
from app.main import app
from app.services import ai_client


@pytest.fixture(autouse=True)
def mock_ai(monkeypatch):
    monkeypatch.setattr(settings, "AI_MOCK", True)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def user(db_session) -> User:
    return make_user(db_session, "tester")


@pytest.fixture
def client(db_session):
    """비로그인 클라이언트. 로그인이 필요하면 /login 으로 실제 로그인한다."""
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client(client, user):
    """tester 로 로그인된 클라이언트."""
    app.dependency_overrides[get_current_user] = lambda: user
    return client


@pytest.fixture
def ai_outcomes(monkeypatch):
    """AI 호출 결과를 순서대로 지정한다. 예외를 넣으면 그 예외가 난다. 호출된 모델 목록을 돌려준다."""
    calls: list[str] = []

    def set_outcomes(*outcomes):
        it = iter(outcomes)

        def fake(model, messages):
            calls.append(model)
            outcome = next(it)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        monkeypatch.setattr(ai_client, "_complete", fake)
        return calls

    return set_outcomes


def make_user(db, username, password_hash="x", is_admin=False) -> User:
    u = User(username=username, password_hash=password_hash, is_admin=is_admin)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u
