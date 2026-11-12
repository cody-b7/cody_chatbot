"""운영: 관리자 로그 조회, 로그 형식, DB 영속성(WAL·백업·복구)."""

import logging
import shutil
import sqlite3

import pytest
from sqlalchemy import create_engine

from app.core import logging as app_logging
from app.db.session import checkpoint_wal
from scripts.backup_db import backup_database
from scripts.restore_db import restore_database

# ---------- 관리자 로그 ----------


def test_admin_logs_require_admin(auth_client):
    assert auth_client.get("/api/admin/logs").status_code == 403


def test_admin_reads_recent_lines(auth_client, user, db_session, monkeypatch, tmp_path):
    user.is_admin = True
    db_session.commit()
    log_file = tmp_path / "app.log"
    log_file.write_text("1\n2\n3\n", encoding="utf-8")
    monkeypatch.setattr(app_logging, "LOG_FILE", log_file)

    assert auth_client.get("/api/admin/logs?limit=2").json() == {"logs": ["2", "3"]}


def test_log_time_carries_timezone():
    """서버 시계는 UTC 라 시간대 없이 찍으면 한국 시간 오후 4시 요청이 07시로 보인다."""
    record = logging.LogRecord("cody.test", logging.INFO, __file__, 0, "hi", None, None)
    record.request_id = "-"
    line = app_logging._ZonedFormatter(offset_hours=9).format(record)
    assert line.split()[1].endswith("+09:00")


# ---------- DB 영속성 ----------
# WAL 모드에서는 커밋된 데이터가 먼저 chatbot.db-wal 에 쌓인다.
# 운영 서버에서 본 파일이 몇 주째 갱신되지 않아 chatbot.db 만 복사하면 데이터가 빠졌다.


def count(path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("select count(*) from notes").fetchone()[0]
    except sqlite3.OperationalError:  # 테이블조차 없음
        return 0
    finally:
        conn.close()


@pytest.fixture
def wal_only_db(tmp_path):
    """데이터가 아직 WAL 에만 있는 DB (연결을 열어 둬야 닫힐 때의 자동 정리가 일어나지 않는다)."""
    path = tmp_path / "chatbot.db"
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("create table notes (id integer primary key)")
    conn.executemany("insert into notes default values", [()] * 3)
    conn.commit()
    yield path
    conn.close()


def test_plain_file_copy_loses_wal_data(wal_only_db, tmp_path):
    shutil.copy2(wal_only_db, tmp_path / "copied.db")
    assert count(tmp_path / "copied.db") == 0


def test_backup_includes_wal_data(wal_only_db, tmp_path):
    assert count(backup_database(wal_only_db, tmp_path / "backups")) == 3


def test_checkpoint_moves_wal_into_main_file(wal_only_db, tmp_path):
    engine = create_engine(f"sqlite:///{wal_only_db}")
    checkpoint_wal(engine)
    engine.dispose()
    shutil.copy2(wal_only_db, tmp_path / "copied.db")
    assert count(tmp_path / "copied.db") == 3


def test_restore_keeps_a_safety_copy(wal_only_db, tmp_path):
    backup = backup_database(wal_only_db, tmp_path / "backups")
    live = tmp_path / "data" / "chatbot.db"
    live.parent.mkdir()
    sqlite3.connect(live).close()

    restore_database(backup, live, tmp_path / "backups")
    assert count(live) == 3
    assert len(list((tmp_path / "backups").glob("pre_restore_*.db"))) == 1
