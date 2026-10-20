"""특정 사용자의 관리자 권한을 변경한다."""

import sys

from app.db import SessionLocal
from app.models import User


def set_admin(username: str, is_admin: bool) -> None:
    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.username == username)
            .first()
        )

        if user is None:
            print(f"사용자를 찾을 수 없습니다: {username}")
            sys.exit(1)

        user.is_admin = is_admin
        db.commit()

        role = "관리자" if is_admin else "일반 사용자"
        print(f"{username} 사용자를 {role}로 변경했습니다.")

    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "사용법: "
            "python scripts/set_admin.py <username> <true|false>"
        )
        sys.exit(1)

    username = sys.argv[1]
    value = sys.argv[2].lower()

    if value not in {"true", "false"}:
        print("두 번째 인자는 true 또는 false여야 합니다.")
        sys.exit(1)

    set_admin(
        username=username,
        is_admin=value == "true",
    )