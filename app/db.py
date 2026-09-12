"""DB 엔진과 세션.

SQLite를 쓰므로 WAL 모드를 켠다. 기본 journal 모드에서는 읽는 중에
쓰기가 막혀서, 대화가 저장되는 동안 로그 조회가 실패할 수 있다.
"""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

_SQLITE_PREFIX = "sqlite:///"
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")


class Base(DeclarativeBase):
    pass


if _is_sqlite:
    # DB 파일이 놓일 디렉터리를 미리 만들어 둔다 (data/ 는 .gitignore 대상)
    Path(settings.DATABASE_URL[len(_SQLITE_PREFIX) :]).resolve().parent.mkdir(
        parents=True, exist_ok=True
    )

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _sqlite_pragma(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
