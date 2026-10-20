"""회원가입 / 로그인 / 로그아웃 테스트."""

from app.models import User
from app.security import verify_password


def test_signup_success(client, db_session):
    """정상 회원가입 시 사용자가 생성되고 로그인 상태가 된다."""
    response = client.post(
        "/signup",
        data={
            "username": "newuser",
            "password": "test1234",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"

    user = (
        db_session.query(User)
        .filter(User.username == "newuser")
        .first()
    )

    assert user is not None
    assert user.password_hash != "test1234"
    assert verify_password("test1234", user.password_hash)


def test_signup_duplicate(client, user):
    """이미 존재하는 username으로 가입할 수 없다."""
    response = client.post(
        "/signup",
        data={
            "username": user.username,
            "password": "test1234",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/signup?error=duplicate"


def test_signup_invalid_username(client):
    """빈 username은 거부한다."""
    response = client.post(
        "/signup",
        data={
            "username": "   ",
            "password": "test1234",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/signup?error=invalid_username"


def test_signup_invalid_password(client):
    """빈 비밀번호는 거부한다."""
    response = client.post(
        "/signup",
        data={
            "username": "newuser",
            "password": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/signup?error=invalid_password"


def test_login_success(client, db_session):
    """올바른 계정으로 로그인할 수 있다."""
    from app.security import hash_password

    user = User(
        username="loginuser",
        password_hash=hash_password("test1234"),
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/login",
        data={
            "username": "loginuser",
            "password": "test1234",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_login_wrong_password(client, db_session):
    """비밀번호가 틀리면 bad_credentials로 처리한다."""
    from app.security import hash_password

    user = User(
        username="loginuser",
        password_hash=hash_password("correct-password"),
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/login",
        data={
            "username": "loginuser",
            "password": "wrong-password",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=bad_credentials"


def test_login_unknown_user(client):
    """존재하지 않는 사용자도 bad_credentials로 처리한다."""
    response = client.post(
        "/login",
        data={
            "username": "does-not-exist",
            "password": "test1234",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login?error=bad_credentials"


def test_logout(auth_client):
    """로그아웃 후 로그인 페이지로 이동한다."""
    response = auth_client.post(
        "/logout",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"