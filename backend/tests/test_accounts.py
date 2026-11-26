"""Sign-up, login, password change and email password reset."""
import logging
from ipaddress import ip_network

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import PasswordResetToken, User


def reg(client, username, email=None, password="Str0ngPassw0rd!"):
    return client.post("/api/auth/register", json={"username": username, "email": email or f"{username}@example.com", "password": password})


def reset_link_from_log(client, caplog, email):
    """In development (no email configured) the link is only ever written to the server log."""
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="emea_guard.accounts"):
        body = client.post("/api/auth/forgot-password", json={"email": email}).json()
    assert "token" not in str(body)                       # never in the API response
    links = [r.getMessage().split("token=")[1] for r in caplog.records if "reset-password?token=" in r.getMessage()]
    return links[-1] if links else None


def me(client, token):
    return client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["username"]


def test_passwords_are_stored_hashed(client, admin, db):
    u = db.execute(select(User).where(User.username == "gov_admin")).scalar_one()
    assert u.email == "gov_admin@example.com"
    assert u.hashed_password.startswith("$2") and "Str0ngPassw0rd!" not in u.hashed_password


def test_new_accounts_after_the_first_are_analysts(client, admin):
    r = reg(client, "second_user")
    assert r.status_code == 201 and r.json()["role"] == "analyst"


def test_registration_validation(client, admin):
    assert reg(client, "ab").status_code == 422                            # username too short
    assert reg(client, "bad name!").status_code == 422                     # invalid characters
    assert reg(client, "weakpw", password="short1").status_code == 422     # too short
    assert reg(client, "nodigit", password="onlylettersherE").status_code == 422
    assert reg(client, "bademail", email="not-an-email").status_code == 422
    assert reg(client, "GOV_ADMIN").status_code == 409                     # username taken (case-insensitive)
    assert reg(client, "other", email="Gov_Admin@Example.com").status_code == 409  # email taken (normalised)
    assert reg(client, "Gov_Admin").status_code == 409                     # case-insensitive


def test_login_with_username_or_email(client, admin):
    by_name = client.post("/api/auth/login", data={"username": "GOV_ADMIN", "password": "Str0ngPassw0rd!"})
    by_mail = client.post("/api/auth/login", data={"username": "Gov_Admin@Example.com", "password": "Str0ngPassw0rd!"})
    assert by_name.status_code == by_mail.status_code == 200
    assert me(client, by_name.json()["access_token"]) == me(client, by_mail.json()["access_token"]) == "gov_admin"
    assert client.post("/api/auth/login", data={"username": "nobody", "password": "Str0ngPassw0rd!"}).status_code == 401


def test_change_password_signs_out_old_tokens(client, admin):
    old = {"Authorization": f"Bearer {reg(client, 'changer').json()['access_token']}"}
    assert client.post("/api/auth/change-password", headers=old, json={"current_password": "wrong-one-1", "new_password": "Br4ndNewPassword"}).status_code == 400
    r = client.post("/api/auth/change-password", headers=old, json={"current_password": "Str0ngPassw0rd!", "new_password": "Br4ndNewPassword"})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=old).status_code == 401           # old session revoked
    new = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=new).json()["username"] == "changer"
    assert client.post("/api/auth/login", data={"username": "changer", "password": "Br4ndNewPassword"}).status_code == 200


def test_forgot_and_reset_password_flow(client, admin, db, caplog):
    reg(client, "forgetful")
    token = reset_link_from_log(client, caplog, "Forgetful@example.com")
    stored = db.execute(select(PasswordResetToken).join(User).where(User.username == "forgetful")).scalars().all()
    assert token and all(t.token_hash != token for t in stored)                  # only the hash is stored
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "weak"}).status_code == 422
    # the weak attempt must not have burned the link
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "Rec0veredPassword"}).status_code == 200
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "An0therPassword"}).status_code == 400  # single use
    login = client.post("/api/auth/login", data={"username": "forgetful", "password": "Rec0veredPassword"})
    assert login.status_code == 200 and me(client, login.json()["access_token"]) == "forgetful"


def test_forgot_password_response_is_identical_for_known_and_unknown_emails(client, admin):
    reg(client, "known_user")
    known = client.post("/api/auth/forgot-password", json={"email": "known_user@example.com"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "nobody-at-all@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


def test_reset_link_is_never_logged_outside_development(client, admin, caplog, monkeypatch):
    from app.config import get_settings
    reg(client, "prod_user")
    for env in ("production", "staging", "prod"):
        monkeypatch.setattr(get_settings(), "environment", env)
        assert reset_link_from_log(client, caplog, "prod_user@example.com") is None
        assert "reset requested" in caplog.text.lower()


def test_new_reset_request_invalidates_previous_link(client, admin, caplog):
    reg(client, "twice")
    first = reset_link_from_log(client, caplog, "twice@example.com")
    reset_link_from_log(client, caplog, "twice@example.com")
    assert client.post("/api/auth/reset-password", json={"token": first, "new_password": "Rec0veredPassword"}).status_code == 400


def test_reset_token_consumption_is_atomic(client, admin, db, caplog):
    from app.services import accounts as A
    reg(client, "atomic_user")
    token = reset_link_from_log(client, caplog, "atomic_user@example.com")
    A.consume_reset_token(db, token)                  # first consumer wins (conditional UPDATE, rowcount 1)
    with pytest.raises(HTTPException) as exc:
        A.consume_reset_token(db, token)              # a concurrent second consumer affects 0 rows
    assert exc.value.status_code == 400
    db.rollback()


def test_usernames_are_unique_case_insensitively_in_the_database(client, admin, db):
    from app.services.accounts import utcnow
    db.add(User(username="Gov_Admin", username_key="gov_admin", email="x@example.com", full_name="x", hashed_password="x",
                app_role="analyst", is_active=True, token_version=0, created_at=utcnow()))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_signup_does_not_reveal_whether_an_email_is_registered(client, admin):
    r = reg(client, "someone_new", email="gov_admin@example.com")
    assert r.status_code == 409 and "already exists" not in r.json()["detail"]


def test_spoofed_forwarded_for_header_cannot_bypass_rate_limit(client, admin):
    codes = [client.post("/api/auth/login", data={"username": "gov_admin", "password": "nope"},
                         headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code for i in range(22)]
    assert 429 in codes


def test_forwarded_address_requires_a_trusted_peer_and_hop_count(monkeypatch):
    from starlette.requests import Request

    from app.config import get_settings
    from app.services.accounts import client_ip

    def request_from(peer, forwarded):
        return Request({"type": "http", "headers": [(b"x-forwarded-for", forwarded)], "client": (peer, 1234)})

    proxy = "172.18.0.5"
    forwarded = b"192.0.2.6, 203.0.113.9, 172.18.0.4"
    settings = get_settings()
    monkeypatch.setattr(settings, "trusted_proxy_hops", 2)
    assert client_ip(request_from(proxy, forwarded)) == proxy  # no configured trusted peers
    monkeypatch.setattr(settings, "trusted_proxy_networks", [ip_network(f"{proxy}/32")])
    assert client_ip(request_from("172.18.0.6", forwarded)) == "172.18.0.6"
    assert client_ip(request_from(proxy, forwarded)) == "203.0.113.9"
    assert client_ip(request_from(proxy, b"203.0.113.9")) == proxy
    assert client_ip(request_from(proxy, b"203.0.113.9, , 172.18.0.4")) == proxy
    monkeypatch.setattr(settings, "trusted_proxy_hops", 0)
    assert client_ip(request_from(proxy, forwarded)) == proxy


def test_admin_cannot_remove_last_admin_and_non_admins_cannot_manage_users(client, admin, analyst):
    users = client.get("/api/users", headers=admin).json()
    me = next(u for u in users if u["username"] == "gov_admin")
    assert client.patch(f"/api/users/{me['id']}", headers=admin, json={"app_role": "analyst"}).status_code == 409
    assert client.get("/api/users", headers=analyst).status_code == 403


def test_login_rate_limit(client, admin):
    codes = [client.post("/api/auth/login", data={"username": "gov_admin", "password": "nope"}).status_code for _ in range(22)]
    assert 429 in codes
