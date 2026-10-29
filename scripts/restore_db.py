"""DB 복구.

서비스를 멈춘 뒤 실행한다:
  sudo systemctl stop cody.service
  ./.venv/bin/python scripts/restore_db.py backups/<백업파일>.db
  sudo systemctl start cody.service

파일을 덮어쓰지 않고 SQLite 백업 API 로 내용을 옮긴다. chatbot.db 만 덮어쓰면
옆에 남아 있던 옛 chatbot.db-wal 이 새 파일 위에 적용되어 DB 가 깨질 수 있다.
복구 직전의 현재 DB 는 backups/pre_restore_*.db 로 한 번 더 백업해 둔다.
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/chatbot.db")
BACKUP_DIR = Path("backups")


def _copy(src_path: Path, dst_path: Path) -> None:
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def restore_database(
    backup_path: Path, db_path: Path = DB_PATH, backup_dir: Path = BACKUP_DIR
) -> None:
    if not backup_path.exists():
        raise FileNotFoundError(f"백업 파일을 찾을 수 없습니다: {backup_path}")

    db_path.parent.mkdir(exist_ok=True)
    backup_dir.mkdir(exist_ok=True)

    # 현재 DB가 있다면 복구 전에 한 번 더 백업
    if db_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety_backup = backup_dir / f"pre_restore_{timestamp}.db"
        _copy(db_path, safety_backup)
        print(f"현재 DB 안전 백업 완료: {safety_backup}")

    _copy(backup_path, db_path)
    print(f"복구 완료: {backup_path} -> {db_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법: python scripts/restore_db.py <백업파일>")
        sys.exit(1)

    restore_database(Path(sys.argv[1]))
