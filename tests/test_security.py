from app.security import hash_password, verify_password


def test_hash_and_verify():
    h = hash_password("test1234")
    assert h != "test1234"          # 평문이 저장되면 안 된다
    assert verify_password("test1234", h)
    assert not verify_password("wrong", h)


def test_long_password_does_not_crash():
    """bcrypt 72바이트 제한에 걸려도 예외가 나면 안 된다."""
    long_pw = "a" * 200
    assert verify_password(long_pw, hash_password(long_pw))


def test_invalid_hash_returns_false():
    assert not verify_password("x", "not-a-hash")
