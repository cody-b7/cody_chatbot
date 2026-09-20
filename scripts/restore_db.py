import shutil
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/chatbot.db")
BACKUP_DIR = Path("backups")


def restore_database(backup_path: Path) -> None:
    if not backup_path.exists():
        raise FileNotFoundError(
            f"백업 파일을 찾을 수 없습니다: {backup_path}"
        )

    DB_PATH.parent.mkdir(exist_ok=True)
    BACKUP_DIR.mkdir(exist_ok=True)

    # 현재 DB가 있다면 복구 전에 한 번 더 백업
    if DB_PATH.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety_backup = BACKUP_DIR / f"pre_restore_{timestamp}.db"
        shutil.copy2(DB_PATH, safety_backup)
        print(f"현재 DB 안전 백업 완료: {safety_backup}")

    shutil.copy2(backup_path, DB_PATH)

    print(f"복구 완료: {backup_path} -> {DB_PATH}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법: python scripts/restore_db.py <백업파일>")
        sys.exit(1)

    restore_database(Path(sys.argv[1]))