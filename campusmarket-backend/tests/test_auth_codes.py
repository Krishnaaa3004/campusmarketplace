"""Email codes: domain checks, signup codes, and the one-time-code login for old accounts."""

import pytest

from app.api.routes import auth as auth_routes
from app.models.user import User


@pytest.fixture(autouse=True)
def no_email(monkeypatch):
    sent = []
    monkeypatch.setattr(auth_routes, "send_otp_email", lambda email, otp: sent.append(email))
    monkeypatch.setattr(auth_routes.settings, "ALLOWED_EMAIL_DOMAINS", ["campus.edu"])
    return sent


def _user(db_session, email):
    db, _ = db_session
    db.expire_all()
    return db.query(User).filter(User.email == email).first()


def test_signup_code_does_not_create_the_account(client, db_session, no_email):
    res = client.post("/api/auth/signup", json={"email": "new@campus.edu", "account_type": "seller"})
    assert res.status_code == 200
    assert no_email == ["new@campus.edu"]
    assert _user(db_session, "new@campus.edu") is None  # created only after the code is verified


def test_signup_refused_for_existing_account(client, users, no_email):
    res = client.post("/api/auth/signup", json={"email": "buyer@campus.edu"})
    assert res.status_code == 409 and "Log in" in res.json()["detail"]
    assert no_email == []


def test_login_code_for_unknown_email_creates_nothing(client, db_session, no_email):
    res = client.post("/api/auth/login-code", json={"email": "stranger@campus.edu"})
    assert res.status_code == 404
    assert "Sign up first" in res.json()["detail"]
    assert _user(db_session, "stranger@campus.edu") is None
    assert no_email == []


def test_login_code_only_for_accounts_without_password(client, users, no_email):
    # buyer has a password -> must use it (or Forgot password)
    res = client.post("/api/auth/login-code", json={"email": "buyer@campus.edu"})
    assert res.status_code == 400 and "password" in res.json()["detail"]
    assert no_email == []


def test_login_code_checks_domain(client):
    assert client.post("/api/auth/login-code", json={"email": "x@gmail.com"}).status_code == 400


def test_owner_can_use_a_personal_email(client, monkeypatch, no_email):
    monkeypatch.setattr(auth_routes.settings, "OWNER_EMAILS", ["Boss@Gmail.com"])
    assert client.post("/api/auth/signup", json={"email": "boss@gmail.com", "account_type": "seller"}).status_code == 200
    assert client.post("/api/auth/password/forgot", json={"email": "boss@gmail.com"}).status_code == 200
    # Any other personal address is still refused.
    assert client.post("/api/auth/signup", json={"email": "someone@gmail.com"}).status_code == 400
    assert client.post("/api/auth/login-code", json={"email": "someone@gmail.com"}).status_code == 400
