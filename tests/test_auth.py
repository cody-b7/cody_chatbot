"""회원가입 / 로그인 / 로그아웃 테스트.

성공은 303 리다이렉트(PRG), 실패는 화면을 바로 그리면서 상태코드로 구분한다.
  형식 오류 422 / 중복·예약 아이디 409 / 로그인 실패 401
"""

import pytest

from app.models import User
from app.security import hash_password, verify_password

GOOD_PASSWORD = "goodpass1"


def _signup(client, username, password=GOOD_PASSWORD):
    return client.post(
        "/signup",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


def _login(client, username, password):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=False,
    )


@pytest.fixture
def member(db_session) -> User:
    """비밀번호가 설정된 가입 회원."""
    u = User(username="member", password_hash=hash_password(GOOD_PASSWORD))
    db_session.add(u)
    db_session.commit()
    return u


# ---------- 회원가입 ----------

def test_signup_success(client, db_session):
    """정상 회원가입 시 사용자가 생성되고 로그인 상태가 된다."""
    res = _signup(client, "newuser")

    assert res.status_code == 303
    assert res.headers["location"] == "/"

    user = db_session.query(User).filter(User.username == "newuser").one()
    assert user.password_hash != GOOD_PASSWORD
    assert verify_password(GOOD_PASSWORD, user.password_hash)


def test_signup_stores_normalized_username(client, db_session):
    _signup(client, "  NewUser ")
    assert db_session.query(User).filter(User.username == "newuser").count() == 1


def test_signup_duplicate(client, member):
    res = _signup(client, member.username)
    assert res.status_code == 409
    assert "이미 쓰고 있는 아이디" in res.text


@pytest.mark.parametrize("variant", ["MEMBER", "Member", " member ", "ｍｅｍｂｅｒ"])
def test_signup_duplicate_lookalike(client, db_session, member, variant):
    """대소문자·공백·전각 문자만 다른 아이디로 다시 가입할 수 없다."""
    res = _signup(client, variant)
    assert res.status_code == 409
    assert db_session.query(User).count() == 1


def test_signup_duplicate_of_legacy_mixed_case_account(client, db_session):
    """정규화 이전에 대문자로 가입한 계정도 중복으로 잡는다."""
    db_session.add(User(username="Legacy", password_hash=hash_password(GOOD_PASSWORD)))
    db_session.commit()

    assert _signup(client, "legacy").status_code == 409


def test_signup_same_username_twice_creates_one_user(client, db_session):
    assert _signup(client, "twice").status_code == 303
    client.cookies.clear()
    assert _signup(client, "twice", "otherpass2").status_code == 409
    assert db_session.query(User).filter(User.username == "twice").count() == 1


@pytest.mark.parametrize("username", ["admin", "Admin", "ADMIN", "root"])
def test_signup_reserved_username(client, username):
    res = _signup(client, username)
    assert res.status_code == 409
    assert "쓸 수 없는 아이디" in res.text


@pytest.mark.parametrize("username", ["   ", "ab", "한글아이디", "has space"])
def test_signup_invalid_username(client, username):
    assert _signup(client, username).status_code == 422


@pytest.mark.parametrize(
    "password",
    ["", "short1", "abcdefgh", "12345678", "pass word1", "newuser99", "a1" * 37],
    ids=["빈값", "짧음", "숫자없음", "영문없음", "공백", "아이디포함", "72바이트초과"],
)
def test_signup_rejects_weak_password(client, db_session, password):
    res = _signup(client, "newuser", password)
    assert res.status_code == 422
    assert db_session.query(User).filter(User.username == "newuser").count() == 0


def test_signup_failure_keeps_entered_username(client):
    """실패해도 입력한 아이디는 남겨 둔다 (다시 치지 않게)."""
    res = _signup(client, "keepme", "short1")
    assert 'value="keepme"' in res.text


# ---------- 로그인 ----------

def test_login_success(client, member):
    res = _login(client, "member", GOOD_PASSWORD)
    assert res.status_code == 303
    assert res.headers["location"] == "/"


def test_login_is_case_insensitive_for_username(client, member):
    assert _login(client, "MEMBER", GOOD_PASSWORD).status_code == 303


def test_login_wrong_password(client, member):
    res = _login(client, "member", "wrongpass1")
    assert res.status_code == 401
    assert "아이디나 비밀번호가 맞지 않습니다" in res.text


def test_login_unknown_user_looks_the_same(client):
    """없는 아이디도 틀린 비밀번호와 같은 응답이어야 가입 여부를 알아낼 수 없다."""
    res = _login(client, "does_not_exist", GOOD_PASSWORD)
    assert res.status_code == 401
    assert "아이디나 비밀번호가 맞지 않습니다" in res.text


def test_login_rejects_password_sharing_first_72_bytes(client, db_session):
    """앞 72바이트만 같고 뒤가 다른 비밀번호로는 로그인되지 않는다."""
    password = "a1" * 36
    db_session.add(User(username="longpw", password_hash=hash_password(password)))
    db_session.commit()

    assert _login(client, "longpw", password).status_code == 303
    client.cookies.clear()
    assert _login(client, "longpw", password + "xyz").status_code == 401


def test_login_does_not_set_session_on_failure(client, member):
    _login(client, "member", "wrongpass1")
    res = client.get("/api/me/stats")
    assert res.status_code == 401


# ---------- 로그아웃 ----------

def test_logout(auth_client):
    res = auth_client.post("/logout", follow_redirects=False)
    assert res.status_code == 303
    assert res.headers["location"] == "/login"


def test_failed_auth_pages_do_not_show_logged_in_menu(client, member):
    """입력한 아이디를 다시 채워 줄 때, 화면이 로그인한 것처럼 메뉴를 띄우면 안 된다."""
    for res in (_signup(client, "keepme", "short1"), _login(client, "member", "wrongpass1")):
        assert 'action="/logout"' not in res.text


# ---------- 정규화 이전에 가입한 계정 ----------

def _legacy(db_session, username, password):
    """정규화 규칙이 생기기 전에 가입한 계정 (아이디가 그대로 저장돼 있음)."""
    u = User(username=username, password_hash=hash_password(password))
    db_session.add(u)
    db_session.commit()
    return u


def test_legacy_accounts_differing_only_in_case_both_log_in(client, db_session):
    """Tester 와 tester 가 따로 있으면 각자 원래 아이디와 비밀번호로 로그인돼야 한다."""
    upper = _legacy(db_session, "Tester", "upperpass1")
    lower = _legacy(db_session, "tester", "lowerpass2")

    res = _login(client, "Tester", "upperpass1")
    assert res.status_code == 303
    assert client.get("/api/me/stats").status_code == 200
    assert _whoami(client, db_session) == upper.id

    client.cookies.clear()
    assert _login(client, "tester", "lowerpass2").status_code == 303
    assert _whoami(client, db_session) == lower.id


def test_legacy_account_with_exact_id_does_not_fall_through_to_other_case(client, db_session):
    """원래 아이디가 있는 계정은 그 계정의 비밀번호로만 로그인된다."""
    _legacy(db_session, "Tester", "upperpass1")
    _legacy(db_session, "tester", "lowerpass2")
    assert _login(client, "Tester", "lowerpass2").status_code == 401


def test_legacy_fullwidth_account_logs_in_with_original_id(client, db_session):
    _legacy(db_session, "ｔｅｓｔｅｒ", "widepass1")
    assert _login(client, "ｔｅｓｔｅｒ", "widepass1").status_code == 303


def test_legacy_mixed_case_account_logs_in_with_other_case(client, db_session):
    """원래 아이디와 정확히 같은 계정이 없으면 대소문자를 무시하고 찾는다."""
    _legacy(db_session, "Legacy", "legacypass1")
    assert _login(client, "legacy", "legacypass1").status_code == 303


def test_case_insensitive_fallback_picks_account_by_password(client, db_session):
    """대소문자만 다른 계정이 여럿이고 입력이 둘 다와 다르면, 비밀번호가 맞는 계정으로."""
    _legacy(db_session, "Tester", "upperpass1")
    lower = _legacy(db_session, "tester", "lowerpass2")
    assert _login(client, "TESTER", "lowerpass2").status_code == 303
    assert _whoami(client, db_session) == lower.id


def _whoami(client, db_session) -> int:
    """지금 쿠키로 로그인된 사용자 id. 세션 하나를 만들어 소유자를 확인한다."""
    from app.models import RoleplaySession

    session_id = client.post(
        "/api/chat", json={"message": "hello", "scenario": "cafe"}
    ).json()["session_id"]
    return db_session.get(RoleplaySession, session_id).user_id
