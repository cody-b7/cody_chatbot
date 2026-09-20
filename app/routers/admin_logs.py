"""관리자용 운영 로그 조회 API."""

from collections import deque
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from app.deps import get_admin_user
from app.models import User

router = APIRouter(prefix="/api/admin", tags=["admin"])

LOG_FILE = Path("logs/app.log")


@router.get("/logs")
def admin_logs(
    limit: int = Query(default=100, ge=1, le=500),
    admin: User = Depends(get_admin_user),
) -> dict[str, list[str]]:
    """최근 운영 로그를 조회한다.

    관리자만 접근할 수 있으며,
    로그 파일의 마지막 limit개 줄만 반환한다.
    """
    if not LOG_FILE.exists():
        return {"logs": []}

    with LOG_FILE.open("r", encoding="utf-8") as file:
        lines = deque(file, maxlen=limit)

    return {
        "logs": [line.rstrip("\n") for line in lines],
    }