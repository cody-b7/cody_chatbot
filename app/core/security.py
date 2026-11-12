"""계정 정책과 비밀번호 해싱.

bcrypt 는 비밀번호를 72바이트까지만 본다. 잘라서 비교하면 앞 72바이트만 같은
다른 비밀번호로도 로그인되므로, 자르지 않고 72바이트를 넘는 입력은 거부한다.
(passlib 은 bcrypt 5 와 호환되지 않아 bcrypt 를 직접 쓴다)
"""

import re
import unicodedata

import bcrypt

MAX_PASSWORD_BYTES = 72
PASSWORD_MIN_LENGTH = 8
_USERNAME_PATTERN = re.compile(r"[a-z0-9_]{3,20}")
RESERVED_USERNAMES = {"admin", "administrator", "root", "system"}


def normalize_username(username: str) -> str:
    """'Tester', ' tester ', 'ｔｅｓｔｅｒ'(전각)를 같은 아이디로 맞춘다."""
    return unicodedata.normalize("NFKC", username).strip().lower()


def check_username(username: str) -> str | None:
    """정규화한 아이디가 정책에 맞으면 None, 아니면 오류 코드."""
    if username in RESERVED_USERNAMES:
        return "reserved_username"
    if not _USERNAME_PATTERN.fullmatch(username):
        return "invalid_username"
    return None


def check_password(password: str, username: str) -> str | None:
    """8자 이상·72바이트 이하, 영문자와 숫자 포함, 공백·아이디 불가. 맞으면 None."""
    if len(password) < PASSWORD_MIN_LENGTH:
        return "password_too_short"
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return "password_too_long"
    if any(ch.isspace() for ch in password):
        return "password_has_space"
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        return "password_too_simple"
    if username in password.lower():
        return "password_contains_username"
    return None


def hash_password(password: str) -> str:
    data = password.encode("utf-8")
    if len(data) > MAX_PASSWORD_BYTES:
        raise ValueError("비밀번호가 72바이트를 넘습니다.")
    return bcrypt.hashpw(data, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    data = password.encode("utf-8")
    if not data or len(data) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(data, password_hash.encode("utf-8"))
    except ValueError:  # 해시 형식이 깨진 경우
        return False
