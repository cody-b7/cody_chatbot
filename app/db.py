"""DB 엔진과 세션.

SQLite를 쓰므로 WAL 모드를 켠다. 기본 journal 모드에서는 읽는 중에
쓰기가 막혀서, 대화가 저장되는 동안 로그 조회가 실패할 수 있다.
"""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
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
        # 커밋이 끝났다고 응답한 데이터는 전원이 나가도 남도록 매 커밋마다 디스크에 쓴다
        cur.execute("PRAGMA synchronous=FULL")
        # WAL 이 100페이지(약 400KB) 쌓이면 본 파일로 옮긴다 (기본값 1000페이지, 약 4MB)
        cur.execute("PRAGMA wal_autocheckpoint=100")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def checkpoint_wal(target: Engine | None = None) -> None:
    """WAL 파일에 쌓인 변경을 본 DB 파일(chatbot.db)로 옮기고 WAL 을 비운다.

    WAL 모드에서 커밋된 데이터는 먼저 chatbot.db-wal 에 쌓이고, 일정량(약 4MB)이
    차야 본 파일로 옮겨진다. 이용량이 적으면 몇 주 동안 본 파일이 갱신되지 않아,
    chatbot.db 만 복사하거나 내려받으면 최근 데이터가 통째로 빠진다.
    앱 시작·종료 때 이 함수를 불러 본 파일을 항상 최신으로 맞춘다.
    """
    target = target or engine
    if target.dialect.name != "sqlite":
        return
    with target.connect() as conn:
        conn.exec_driver_sql("PRAGMA wal_checkpoint(TRUNCATE)")


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
