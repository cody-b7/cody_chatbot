"""관리자 운영 로그 조회."""

from collections import deque

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_admin_user
from app.core import logging as app_logging
from app.db.models import User

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/logs", summary="최근 운영 로그 (관리자)")
def read_logs(
    limit: int = Query(default=100, ge=1, le=500),
    admin: User = Depends(get_admin_user),
) -> dict[str, list[str]]:
    path = app_logging.LOG_FILE
    if not path.exists():
        return {"logs": []}
    with path.open(encoding="utf-8") as file:
        return {"logs": [line.rstrip("\n") for line in deque(file, maxlen=limit)]}
