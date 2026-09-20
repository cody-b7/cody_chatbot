import shutil
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/chatbot.db")
BACKUP_DIR = Path("backups")


def backup_database() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DB 파일을 찾을 수 없습니다: {DB_PATH}")

    BACKUP_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"chatbot_{timestamp}.db"

    shutil.copy2(DB_PATH, backup_path)

    print(f"백업 완료: {backup_path}")


if __name__ == "__main__":
    backup_database()