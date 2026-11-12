"""DB 엔진·세션과 SQLite 영속성 설정.

WAL 모드에서 커밋된 데이터는 먼저 chatbot.db-wal 에 쌓였다가 본 파일로 옮겨진다.
운영 서버에서 본 파일이 몇 주째 갱신되지 않아 chatbot.db 만 복사한 백업에서
데이터가 빠진 적이 있어서, 시작·종료 때 checkpoint_wal 로 본 파일을 최신으로 맞춘다.
"""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
if _is_sqlite:
    Path(settings.DATABASE_URL.removeprefix("sqlite:///")).resolve().parent.mkdir(
        parents=True, exist_ok=True
    )

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    pass


if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragma(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")  # 읽는 중에도 쓸 수 있게
        cur.execute("PRAGMA synchronous=FULL")  # 커밋한 데이터는 전원이 나가도 남게
        cur.execute("PRAGMA wal_autocheckpoint=100")  # WAL 400KB 마다 본 파일로 (기본 4MB)
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def checkpoint_wal(target: Engine | None = None) -> None:
    """WAL 에 쌓인 변경을 본 DB 파일로 옮기고 WAL 을 비운다."""
    target = target or engine
    if target.dialect.name == "sqlite":
        with target.connect() as conn:
            conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
