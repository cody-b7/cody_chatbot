"""회원가입·로그인·계정 정책.

성공은 303 이동, 실패는 화면을 다시 그리며 422(형식) / 409(중복·예약) / 401(로그인 실패).
"""

import pytest

from app.core.security import (
    check_password,
    check_username,
    hash_password,
    normalize_username,
    verify_password,
)
from app.db.models import RoleplaySession, User
from tests.conftest import make_user

GOOD = "goodpass1"


def signup(client, username, password=GOOD):
    return client.post("/signup", data={"username": username, "password": password},
                       follow_redirects=False)


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password},
                       follow_redirects=False)


def logged_in_user_id(client, db) -> int:
    """지금 쿠키의 사용자. 세션을 하나 만들어 그 소유자로 확인한다."""
    session_id = client.post("/api/sessions", json={"scenario": "cafe"}).json()["id"]
    return db.get(RoleplaySession, session_id).user_id


# ---------- 정책 (단위) ----------

@pytest.mark.parametrize("raw", ["Tester", " tester ", "TESTER", "ｔｅｓｔｅｒ"])
def test_lookalike_usernames_normalize_to_one(raw):
    assert normalize_username(raw) == "tester"


@pytest.mark.parametrize("username, expected", [
    ("user_01", None), ("ab", "invalid_username"), ("a" * 21, "invalid_username"),
    ("한글아이디", "invalid_username"), ("admin", "reserved_username"),
])
def test_username_policy(username, expected):
    assert check_username(username) == expected


@pytest.mark.parametrize("password, expected", [
    ("goodpass1", None), ("short1", "password_too_short"), ("abcdefgh", "password_too_simple"),
    ("12345678", "password_too_simple"), ("pass word1", "password_has_space"),
    ("tester123", "password_contains_username"), ("a1" * 37, "password_too_long"),
])
def test_password_policy(password, expected):
    assert check_password(password, "tester") == expected


def test_password_over_72_bytes_is_not_truncated():
    """bcrypt 는 72바이트까지만 본다. 잘라서 비교하면 뒤가 다른 비밀번호도 통과한다."""
    h = hash_password("a1" * 36)
    assert verify_password("a1" * 36, h)
    assert not verify_password("a1" * 36 + "tail", h)


# ---------- 회원가입 ----------

def test_signup_stores_normalized_username_and_hash(client, db_session):
    res = signup(client, "  NewUser ")
    assert res.status_code == 303
    user = db_session.query(User).filter(User.username == "newuser").one()
    assert verify_password(GOOD, user.password_hash)


@pytest.mark.parametrize("variant", ["tester", "TESTER", " tester ", "ｔｅｓｔｅｒ"])
def test_signup_blocks_duplicate_lookalikes(client, db_session, user, variant):
    assert signup(client, variant).status_code == 409
    assert db_session.query(User).count() == 1


def test_signup_reserved_username(client):
    res = signup(client, "Admin")
    assert res.status_code == 409
    assert "쓸 수 없는 아이디" in res.text


@pytest.mark.parametrize("username, password", [("ab", GOOD), ("newuser", "short1")])
def test_signup_rejects_invalid_input(client, db_session, username, password):
    res = signup(client, username, password)
    assert res.status_code == 422
    assert db_session.query(User).count() == 0


def test_failed_signup_keeps_username_without_logged_in_menu(client):
    res = signup(client, "keepme", "short1")
    assert 'value="keepme"' in res.text
    assert 'action="/logout"' not in res.text


# ---------- 로그인 ----------

def test_login_success_and_logout(client, db_session):
    make_user(db_session, "member", hash_password(GOOD))
    assert login(client, "member", GOOD).status_code == 303
    assert client.get("/api/stats").status_code == 200
    assert client.post("/logout", follow_redirects=False).headers["location"] == "/login"
    assert client.get("/api/stats").status_code == 401


@pytest.mark.parametrize("username, password", [("member", "wrongpass1"), ("nobody", GOOD)])
def test_login_failure_looks_the_same(client, db_session, username, password):
    """없는 아이디와 틀린 비밀번호를 구분할 수 없어야 가입 여부가 새지 않는다."""
    make_user(db_session, "member", hash_password(GOOD))
    res = login(client, username, password)
    assert res.status_code == 401
    assert "아이디나 비밀번호가 맞지 않습니다" in res.text


def test_legacy_case_variants_each_log_in_with_own_password(client, db_session):
    """정규화 이전에 Tester 와 tester 가 따로 가입했으면 각자 원래 아이디로 로그인된다."""
    upper = make_user(db_session, "Tester", hash_password("upperpass1"))
    lower = make_user(db_session, "tester", hash_password("lowerpass2"))

    assert login(client, "Tester", "lowerpass2").status_code == 401  # 남의 비밀번호로는 안 됨
    assert login(client, "Tester", "upperpass1").status_code == 303
    assert logged_in_user_id(client, db_session) == upper.id

    client.cookies.clear()
    # 입력과 정확히 같은 아이디가 없으면 대소문자를 무시하고 비밀번호가 맞는 계정으로
    assert login(client, "TESTER", "lowerpass2").status_code == 303
    assert logged_in_user_id(client, db_session) == lower.id


def test_legacy_fullwidth_account_logs_in_with_original_id(client, db_session):
    make_user(db_session, "ｔｅｓｔｅｒ", hash_password("widepass1"))
    assert login(client, "ｔｅｓｔｅｒ", "widepass1").status_code == 303
