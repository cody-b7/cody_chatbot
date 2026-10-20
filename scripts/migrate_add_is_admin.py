"""기존 SQLite users 테이블에 is_admin 컬럼을 추가한다.

이미 컬럼이 존재하면 아무 작업도 하지 않는다.
기존 사용자는 모두 일반 사용자(False)로 유지한다.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("data/chatbot.db")


def migrate() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DB 파일을 찾을 수 없습니다: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)

    try:
        columns = conn.execute("PRAGMA table_info(users)").fetchall()
        column_names = {column[1] for column in columns}

        if "is_admin" in column_names:
            print("is_admin 컬럼이 이미 존재합니다.")
            return

        conn.execute(
            """
            ALTER TABLE users
            ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0
            """
        )
        conn.commit()

        print("is_admin 컬럼 추가 완료")

    finally:
        conn.close()


if __name__ == "__main__":
    migrate()