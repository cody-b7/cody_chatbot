"""비밀번호 해싱.

passlib 1.7.4 는 bcrypt 5.x 와 호환되지 않는다 (내부에서 제거된
bcrypt.__about__ 을 읽다가 죽는다). 그래서 bcrypt 를 직접 쓴다.

bcrypt 는 비밀번호를 72바이트까지만 본다. 그보다 길면 조용히 잘려서
"긴 비밀번호가 사실은 검증되지 않는" 상태가 되므로, 스키마에서 길이를
제한하고 여기서도 같은 기준으로 자른다.
"""

import bcrypt

MAX_PASSWORD_BYTES = 72


def _encode(password: str) -> bytes:
    return password.encode("utf-8")[:MAX_PASSWORD_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_encode(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False
