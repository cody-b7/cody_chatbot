"""계정 정책과 비밀번호 해싱.

passlib 1.7.4 는 bcrypt 5.x 와 호환되지 않는다 (내부에서 제거된
bcrypt.__about__ 을 읽다가 죽는다). 그래서 bcrypt 를 직접 쓴다.

bcrypt 는 비밀번호를 72바이트까지만 본다. 그보다 긴 입력을 잘라서 비교하면
"앞 72바이트만 같으면 뒤가 달라도 로그인되는" 구멍이 생긴다. 그래서 자르지
않고, 72바이트를 넘는 비밀번호는 가입에서도 로그인에서도 거부한다.
"""

import re
import unicodedata

import bcrypt

MAX_PASSWORD_BYTES = 72
PASSWORD_MIN_LENGTH = 8

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 20
_USERNAME_PATTERN = re.compile(r"^[a-z0-9_]+$")

# 관리자처럼 보일 수 있는 아이디는 막는다 (권한은 is_admin 으로만 준다)
RESERVED_USERNAMES = {"admin", "administrator", "root", "system"}


def normalize_username(username: str) -> str:
    """아이디를 비교·저장용 형태로 맞춘다.

    "Tester", " tester ", "ｔｅｓｔｅｒ"(전각) 이 모두 같은 아이디로 취급되도록
    공백 제거 → 유니코드 정규화(NFKC) → 소문자 순서로 바꾼다.
    이렇게 하지 않으면 사람 눈에는 같은 아이디가 여러 번 가입된다.
    """
    return unicodedata.normalize("NFKC", username).strip().lower()


def check_username(username: str) -> str | None:
    """정규화된 아이디가 정책에 맞으면 None, 아니면 오류 코드."""
    if username in RESERVED_USERNAMES:
        return "reserved_username"
    if not USERNAME_MIN_LENGTH <= len(username) <= USERNAME_MAX_LENGTH:
        return "invalid_username"
    if not _USERNAME_PATTERN.match(username):
        return "invalid_username"
    return None


def check_password(password: str, username: str) -> str | None:
    """비밀번호가 정책에 맞으면 None, 아니면 오류 코드.

    - 8자 이상, 72바이트 이하
    - 영문자와 숫자를 각각 하나 이상
    - 공백 없음
    - 아이디를 그대로 포함하지 않음
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return "password_too_short"
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        return "password_too_long"
    if any(ch.isspace() for ch in password):
        return "password_has_space"
    has_letter = any(ch.isascii() and ch.isalpha() for ch in password)
    has_digit = any(ch.isdigit() for ch in password)
    if not (has_letter and has_digit):
        return "password_too_simple"
    if username and username in password.lower():
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
        # 잘라서 비교하지 않는다 — 앞부분만 같은 다른 비밀번호가 통과하게 된다
        return False
    try:
        return bcrypt.checkpw(data, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False
