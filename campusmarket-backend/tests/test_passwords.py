"""Password login: signup with a password, login, lockout, the no-password fallback,
the mandatory set-password step, and forgot/reset."""

import pytest

from app.api.routes import auth as auth_routes
from app.models.otp import OTPCode
from app.models.user import User
from conftest import TEST_PASSWORD, _user

GOOD = "newpass123"


@pytest.fixture(autouse=True)
def mailbox(monkeypatch):
    """Capture sent codes instead of emailing them: {email: latest code}."""
    box = {}
    monkeypatch.setattr(auth_routes, "send_otp_email", lambda email, otp: box.__setitem__(email, otp))
    monkeypatch.setattr(auth_routes.settings, "ALLOWED_EMAIL_DOMAINS", ["campus.edu"])
    return box


@pytest.fixture
def legacy(db_session):
    """An account from before passwords existed: verified, profile done, no password."""
    db, _ = db_session
    return _user(db, "legacy@campus.edu", password_hash=None, account_type="seller")


def login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def bearer(res):
    return {"Authorization": f"Bearer {res.json()['token']}"}


def fetch(db_session, email):
    db, _ = db_session
    db.expire_all()
    return db.query(User).filter(User.email == email).first()


# ---------- signup ----------


def test_signup_with_password(client, db_session, mailbox):
    assert client.post("/api/auth/signup", json={"email": "riya@campus.edu", "account_type": "seller"}).status_code == 200
    res = client.post("/api/auth/signup/verify", json={
        "email": "riya@campus.edu", "otp": mailbox["riya@campus.edu"], "account_type": "seller",
        "password": GOOD, "confirm_password": GOOD,
    })
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["user"]["has_password"] is True and body["user"]["verified"] is True
    assert body["user"]["account_type"] == "seller"
    assert "password_hash" not in body["user"]
    user = fetch(db_session, "riya@campus.edu")
    assert user.password_hash.startswith("$argon2") and GOOD not in user.password_hash
    # ...and the new password works.
    assert login(client, "riya@campus.edu", GOOD).status_code == 200


@pytest.mark.parametrize("password,confirm,msg", [
    ("short1", "short1", "at least 8"),
    ("abcdefgh", "abcdefgh", "letter and one number"),
    ("12345678", "12345678", "letter and one number"),
    ("abc12345", "abc12346", "don't match"),
])
def test_signup_password_rules(client, db_session, mailbox, password, confirm, msg):
    client.post("/api/auth/signup", json={"email": "riya@campus.edu"})
    res = client.post("/api/auth/signup/verify", json={
        "email": "riya@campus.edu", "otp": mailbox["riya@campus.edu"], "password": password, "confirm_password": confirm,
    })
    assert res.status_code == 422 and msg in str(res.json()["detail"])
    assert fetch(db_session, "riya@campus.edu") is None


def test_signup_wrong_code_creates_nothing(client, db_session, mailbox):
    client.post("/api/auth/signup", json={"email": "riya@campus.edu"})
    res = client.post("/api/auth/signup/verify", json={
        "email": "riya@campus.edu", "otp": "000000" if mailbox["riya@campus.edu"] != "000000" else "111111",
        "password": GOOD, "confirm_password": GOOD,
    })
    assert res.status_code == 400 and fetch(db_session, "riya@campus.edu") is None


# ---------- password login ----------


def test_password_login_success(client, users):
    res = login(client, "buyer@campus.edu", TEST_PASSWORD)
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "buyer@campus.edu" and res.json()["token"]
    assert client.get("/api/users/me", headers=bearer(res)).status_code == 200


def test_password_login_failure_is_generic(client, users):
    wrong_pw = login(client, "buyer@campus.edu", "nope12345")
    no_user = login(client, "ghost@campus.edu", "nope12345")
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json()["detail"] == no_user.json()["detail"] == "Invalid email or password"


def test_lockout_after_repeated_failures(client, db_session, users):
    for _ in range(auth_routes.settings.LOGIN_MAX_FAILURES - 1):
        assert login(client, "buyer@campus.edu", "wrong12345").status_code == 401
    locked = login(client, "buyer@campus.edu", "wrong12345")
    assert locked.status_code == 429
    # Even the right password is refused while locked.
    assert login(client, "buyer@campus.edu", TEST_PASSWORD).status_code == 429
    assert fetch(db_session, "buyer@campus.edu").locked_until is not None


def test_ip_rate_limit(client, users, monkeypatch):
    monkeypatch.setattr(auth_routes._login_ip_limiter, "limit", 3)
    for email in ["a@campus.edu", "b@campus.edu", "c@campus.edu"]:
        assert login(client, email, "whatever123").status_code == 401
    assert login(client, "buyer@campus.edu", TEST_PASSWORD).status_code == 429


# ---------- accounts without a password ----------


def test_existing_user_without_password_falls_back_to_code(client, legacy, mailbox):
    res = login(client, "legacy@campus.edu", "anything123")
    assert res.status_code == 403 and res.json()["detail"]["code"] == "password_not_set"

    assert client.post("/api/auth/login-code", json={"email": "legacy@campus.edu"}).status_code == 200
    res = client.post("/api/auth/login/otp", json={"email": "legacy@campus.edu", "otp": mailbox["legacy@campus.edu"]})
    assert res.status_code == 200
    assert res.json()["user"]["has_password"] is False  # -> the app shows the mandatory modal


def test_protected_routes_blocked_until_password_set(client, legacy, mailbox):
    client.post("/api/auth/login-code", json={"email": "legacy@campus.edu"})
    h = bearer(client.post("/api/auth/login/otp", json={"email": "legacy@campus.edu", "otp": mailbox["legacy@campus.edu"]}))

    # /users/me works (so the app can ask for a password)...
    assert client.get("/api/users/me", headers=h).json()["has_password"] is False
    # ...but everything else is refused.
    for method, path, body in [
        ("get", "/api/listings", None),
        ("get", "/api/resources", None),
        ("get", "/api/notifications", None),
        ("patch", "/api/users/me", {"name": "x"}),
        ("post", "/api/listings", {"title": "x", "category": "Sports", "condition": "Good", "pickup_spot": "x"}),
    ]:
        res = getattr(client, method)(path, headers=h, **({"json": body} if body else {}))
        assert res.status_code == 403, path
        assert res.json()["detail"]["code"] == "password_required", path

    # Setting a password unlocks everything.
    res = client.post("/api/auth/set-password", json={"password": GOOD, "confirm_password": GOOD}, headers=h)
    assert res.status_code == 200 and res.json()["user"]["has_password"] is True
    fresh = bearer(res)
    assert client.get("/api/listings", headers=fresh).status_code == 200
    assert login(client, "legacy@campus.edu", GOOD).status_code == 200


def test_set_password_refused_when_one_exists(client, auth):
    res = client.post("/api/auth/set-password", json={"password": GOOD, "confirm_password": GOOD}, headers=auth("buyer"))
    assert res.status_code == 409


def test_set_password_validates(client, legacy, mailbox):
    client.post("/api/auth/login-code", json={"email": "legacy@campus.edu"})
    h = bearer(client.post("/api/auth/login/otp", json={"email": "legacy@campus.edu", "otp": mailbox["legacy@campus.edu"]}))
    res = client.post("/api/auth/set-password", json={"password": "abc", "confirm_password": "abc"}, headers=h)
    assert res.status_code == 422


def test_code_login_refused_for_accounts_with_password(client, users):
    res = client.post("/api/auth/login/otp", json={"email": "buyer@campus.edu", "otp": "123456"})
    assert res.status_code == 400


# ---------- forgot / reset ----------


def test_password_reset(client, db_session, users, mailbox):
    # lock the account first: reset should also unlock it
    for _ in range(auth_routes.settings.LOGIN_MAX_FAILURES):
        login(client, "buyer@campus.edu", "wrong12345")

    res = client.post("/api/auth/password/forgot", json={"email": "buyer@campus.edu"})
    assert res.status_code == 200
    res = client.post("/api/auth/password/reset", json={
        "email": "buyer@campus.edu", "otp": mailbox["buyer@campus.edu"], "password": GOOD, "confirm_password": GOOD,
    })
    assert res.status_code == 200 and res.json()["token"]
    assert login(client, "buyer@campus.edu", TEST_PASSWORD).status_code == 401  # old password gone
    assert login(client, "buyer@campus.edu", GOOD).status_code == 200
    assert fetch(db_session, "buyer@campus.edu").locked_until is None


def test_forgot_password_does_not_reveal_accounts(client, mailbox):
    known = client.post("/api/auth/password/forgot", json={"email": "buyer@campus.edu"})
    unknown = client.post("/api/auth/password/forgot", json={"email": "ghost@campus.edu"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert "ghost@campus.edu" not in mailbox


def test_reset_code_is_single_use_and_purpose_bound(client, users, mailbox):
    client.post("/api/auth/password/forgot", json={"email": "buyer@campus.edu"})
    code = mailbox["buyer@campus.edu"]
    body = {"email": "buyer@campus.edu", "otp": code, "password": GOOD, "confirm_password": GOOD}
    assert client.post("/api/auth/password/reset", json=body).status_code == 200
    assert client.post("/api/auth/password/reset", json=body).status_code == 400  # used up
    # A signup code can't be used to reset a password.
    client.post("/api/auth/signup", json={"email": "riya@campus.edu"})
    res = client.post("/api/auth/password/reset", json={**body, "email": "riya@campus.edu", "otp": mailbox["riya@campus.edu"]})
    assert res.status_code == 400


def test_wrong_codes_burn_the_code(client, db_session, users, mailbox):
    client.post("/api/auth/password/forgot", json={"email": "buyer@campus.edu"})
    real = mailbox["buyer@campus.edu"]
    wrong = "000000" if real != "000000" else "111111"
    body = {"email": "buyer@campus.edu", "password": GOOD, "confirm_password": GOOD}
    for _ in range(auth_routes.settings.OTP_MAX_ATTEMPTS):
        assert client.post("/api/auth/password/reset", json={**body, "otp": wrong}).status_code == 400
    # After too many guesses even the right code is refused.
    res = client.post("/api/auth/password/reset", json={**body, "otp": real})
    assert res.status_code == 400 and "Too many" in res.json()["detail"]



# ---------- sessions ----------


def _old_session(user):
    """A session issued a minute ago, e.g. one an attacker stole earlier."""
    from datetime import datetime, timedelta, timezone

    import jwt

    from app.core.config import settings

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": str(user.id), "iat": int((now - timedelta(minutes=1)).timestamp()), "exp": now + timedelta(days=1)},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def test_password_reset_logs_out_older_sessions(client, users, mailbox):
    stolen = _old_session(users["buyer"])
    assert client.get("/api/users/me", headers=stolen).status_code == 200

    client.post("/api/auth/password/forgot", json={"email": "buyer@campus.edu"})
    res = client.post("/api/auth/password/reset", json={
        "email": "buyer@campus.edu", "otp": mailbox["buyer@campus.edu"], "password": GOOD, "confirm_password": GOOD,
    })
    assert res.status_code == 200

    gone = client.get("/api/users/me", headers=stolen)
    assert gone.status_code == 401 and "Log in again" in gone.json()["detail"]
    assert client.get("/api/users/me", headers=bearer(res)).status_code == 200  # the new session works


def test_setting_first_password_returns_working_session(client, legacy):
    old = _old_session(legacy)
    res = client.post("/api/auth/set-password", json={"password": GOOD, "confirm_password": GOOD}, headers=old)
    assert res.status_code == 200 and res.json()["token"]
    assert client.get("/api/listings", headers=old).status_code == 401  # pre-change session is gone
    assert client.get("/api/listings", headers=bearer(res)).status_code == 200


def test_sessions_last_30_days_and_renew(client, users):
    import jwt

    from app.core.config import settings

    res = login(client, "buyer@campus.edu", TEST_PASSWORD)
    claims = jwt.decode(res.json()["token"], settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert claims["exp"] - claims["iat"] == 30 * 24 * 3600

    renewed = client.post("/api/auth/refresh", headers=bearer(res))
    assert renewed.status_code == 200 and renewed.json()["token"]
    assert client.get("/api/users/me", headers=bearer(renewed)).status_code == 200
    assert client.post("/api/auth/refresh").status_code in (401, 403)  # no session, nothing to renew


def test_dead_session_cannot_renew(client, users, mailbox):
    stolen = _old_session(users["buyer"])
    client.post("/api/auth/password/forgot", json={"email": "buyer@campus.edu"})
    client.post("/api/auth/password/reset", json={
        "email": "buyer@campus.edu", "otp": mailbox["buyer@campus.edu"], "password": GOOD, "confirm_password": GOOD,
    })
    assert client.post("/api/auth/refresh", headers=stolen).status_code == 401
