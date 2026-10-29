"""데이터 영속성.

SQLite WAL 모드에서는 커밋된 데이터가 먼저 chatbot.db-wal 에 쌓인다.
운영 서버에서 실제로 본 파일(chatbot.db)이 몇 주째 갱신되지 않고 모든 데이터가
WAL 에만 있던 적이 있다. 이 상태에서 chatbot.db 만 복사하면 데이터가 빠진다.
"""

import logging
import shutil
import sqlite3

import pytest
from sqlalchemy import create_engine

from app.db import checkpoint_wal
from app.logging_config import _ZonedFormatter
from scripts.backup_db import backup_database
from scripts.restore_db import restore_database


def _count(path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("select count(*) from notes").fetchone()[0]
    except sqlite3.OperationalError:  # 테이블조차 없음
        return 0
    finally:
        conn.close()


@pytest.fixture
def wal_only_db(tmp_path):
    """데이터가 아직 WAL 에만 있는 DB. 연결을 열어 둬야 닫힐 때의 자동 정리가 일어나지 않는다."""
    path = tmp_path / "chatbot.db"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")  # 자동으로 본 파일에 옮기지 않게
    conn.execute("create table notes (id integer primary key, body text)")
    conn.executemany("insert into notes (body) values (?)", [("a",), ("b",), ("c",)])
    conn.commit()
    yield path
    conn.close()


def test_copying_only_the_db_file_loses_wal_data(wal_only_db, tmp_path):
    """예전 백업 방식(shutil.copy)이 왜 위험한지 보여준다."""
    copied = tmp_path / "copied.db"
    shutil.copy2(wal_only_db, copied)
    assert _count(copied) == 0


def test_backup_includes_data_still_in_wal(wal_only_db, tmp_path):
    backup = backup_database(wal_only_db, tmp_path / "backups")
    assert _count(backup) == 3


def test_checkpoint_moves_wal_into_main_file(wal_only_db, tmp_path):
    engine = create_engine(f"sqlite:///{wal_only_db}")
    try:
        checkpoint_wal(engine)
    finally:
        engine.dispose()

    assert wal_only_db.with_name("chatbot.db-wal").stat().st_size == 0
    copied = tmp_path / "copied.db"
    shutil.copy2(wal_only_db, copied)
    assert _count(copied) == 3, "체크포인트 후에는 본 파일만으로도 데이터가 온전해야 한다"


def test_restore_replaces_contents_safely(tmp_path):
    backup = tmp_path / "backup.db"
    conn = sqlite3.connect(backup)
    conn.execute("create table notes (id integer primary key, body text)")
    conn.execute("insert into notes (body) values ('from backup')")
    conn.commit()
    conn.close()

    live = tmp_path / "data" / "chatbot.db"
    live.parent.mkdir()
    conn = sqlite3.connect(live)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("create table notes (id integer primary key, body text)")
    conn.executemany("insert into notes (body) values (?)", [("x",), ("y",)])
    conn.commit()
    conn.close()

    restore_database(backup, live, tmp_path / "backups")

    conn = sqlite3.connect(live)
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert conn.execute("select body from notes").fetchall() == [("from backup",)]
    conn.close()
    # 복구 직전 상태도 남아 있어야 한다
    safety = list((tmp_path / "backups").glob("pre_restore_*.db"))
    assert len(safety) == 1 and _count(safety[0]) == 2


def test_log_time_carries_timezone():
    """서버 시계는 UTC 라서, 시간대 없이 찍으면 한국 시간 오후 4시 요청이 07시로 보인다."""
    formatter = _ZonedFormatter("%(asctime)s %(message)s", offset_hours=9)
    record = logging.LogRecord("cody.test", logging.INFO, __file__, 0, "hi", None, None)
    assert formatter.format(record).split(" ")[0].endswith("+09:00")
