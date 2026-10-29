"""DB 백업.

파일 복사(shutil.copy)로 백업하면 안 된다. WAL 모드에서는 최근에 커밋된
데이터가 chatbot.db 가 아니라 chatbot.db-wal 에 들어 있어서, chatbot.db 만
복사하면 그 데이터가 백업에서 빠진다. SQLite 의 백업 API 는 WAL 내용까지 포함한
일관된 스냅샷을 만들고, 서버가 돌고 있는 중에도 안전하게 쓸 수 있다.

사용법: python scripts/backup_db.py
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/chatbot.db")
BACKUP_DIR = Path("backups")


def backup_database(db_path: Path = DB_PATH, backup_dir: Path = BACKUP_DIR) -> Path:
    if not db_path.exists():
        raise FileNotFoundError(f"DB 파일을 찾을 수 없습니다: {db_path}")

    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"chatbot_{timestamp}.db"

    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(backup_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    print(f"백업 완료: {backup_path}")
    return backup_path


if __name__ == "__main__":
    backup_database()
