"""계정 정책과 비밀번호 해싱."""

import pytest

from app.security import (
    check_password,
    check_username,
    hash_password,
    normalize_username,
    verify_password,
)


def test_hash_and_verify():
    h = hash_password("test1234")
    assert h != "test1234"          # 평문이 저장되면 안 된다
    assert verify_password("test1234", h)
    assert not verify_password("wrong", h)


def test_password_over_72_bytes_is_not_truncated():
    """bcrypt 는 72바이트까지만 본다. 잘라서 비교하면 뒤가 다른 비밀번호도 통과한다."""
    base = "a1" * 36                 # 정확히 72바이트
    h = hash_password(base)
    assert verify_password(base, h)
    assert not verify_password(base + "different-tail", h)


def test_hashing_over_72_bytes_is_refused():
    with pytest.raises(ValueError):
        hash_password("a1" * 100)


def test_empty_password_never_verifies():
    assert not verify_password("", hash_password("test1234"))


def test_invalid_hash_returns_false():
    assert not verify_password("x", "not-a-hash")


# ---------- 아이디 정규화 ----------

@pytest.mark.parametrize("raw", ["Tester", " tester ", "TESTER", "ｔｅｓｔｅｒ"])
def test_lookalike_usernames_normalize_to_one(raw):
    """사람 눈에 같은 아이디는 같은 값이 되어야 중복 가입을 막을 수 있다."""
    assert normalize_username(raw) == "tester"


@pytest.mark.parametrize(
    "username, expected",
    [
        ("tester", None),
        ("user_01", None),
        ("ab", "invalid_username"),            # 너무 짧음
        ("a" * 21, "invalid_username"),        # 너무 김
        ("한글아이디", "invalid_username"),
        ("has space", "invalid_username"),
        ("admin", "reserved_username"),
        ("root", "reserved_username"),
    ],
)
def test_username_policy(username, expected):
    assert check_username(username) == expected


# ---------- 비밀번호 정책 ----------

@pytest.mark.parametrize(
    "password, expected",
    [
        ("goodpass1", None),
        ("short1", "password_too_short"),
        ("abcdefgh", "password_too_simple"),   # 숫자 없음
        ("12345678", "password_too_simple"),   # 영문자 없음
        ("pass word1", "password_has_space"),
        ("tester123", "password_contains_username"),
        ("a1" * 37, "password_too_long"),      # 74바이트
    ],
)
def test_password_policy(password, expected):
    assert check_password(password, "tester") == expected
