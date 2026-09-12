"""회원가입 / 로그인 / 로그아웃.

TODO(B): 이 파일 전체가 B의 작업 범위다. 아래는 라우트 자리만 잡아둔 것이며,
         경로와 리다이렉트 규칙만 유지하면 내부 구현은 자유롭게 바꿔도 된다.

구현 메모
  - 비밀번호는 app/security.py 의 hash_password / verify_password 사용
    (passlib 은 bcrypt 5.x 와 호환되지 않아 제거했다. 평문 저장 금지)
  - 로그인 성공 시 request.session["user_id"] = user.id
  - 로그아웃은 request.session.clear()
  - 완료하면 app/deps.py 의 DEV_AUTH_BYPASS 블록을 삭제할 것
  - 로그로 login_success / login_failed 를 남길 것
"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session as DbSession

from app.db import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"])


@router.post("/signup")
def signup(request: Request, db: DbSession = Depends(get_db)):
    raise NotImplementedError("TODO(B): 회원가입 구현")


@router.post("/login")
def login(request: Request, db: DbSession = Depends(get_db)):
    raise NotImplementedError("TODO(B): 로그인 구현")


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}
