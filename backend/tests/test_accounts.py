"""Sign-up, login, password change and email password reset."""
from sqlalchemy import select

from app.models import PasswordResetToken, User


def reg(client, username, email=None, password="Str0ngPassw0rd!"):
    return client.post("/api/auth/register", json={"username": username, "email": email or f"{username}@example.com", "password": password})


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


def test_login_with_username_or_email(client, admin):
    assert client.post("/api/auth/login", data={"username": "gov_admin", "password": "Str0ngPassw0rd!"}).status_code == 200
    assert client.post("/api/auth/login", data={"username": "GOV_ADMIN@example.com", "password": "Str0ngPassw0rd!"}).status_code == 200
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


def test_forgot_and_reset_password_flow(client, admin, db):
    reg(client, "forgetful")
    unknown = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"}).json()
    assert "dev_reset_link" not in unknown                                     # no account enumeration
    r = client.post("/api/auth/forgot-password", json={"email": "Forgetful@example.com"}).json()
    token = r["dev_reset_link"].split("token=")[1]                            # SMTP off in tests -> dev link returned
    stored = db.execute(select(PasswordResetToken).join(User).where(User.username == "forgetful")).scalars().all()
    assert all(t.token_hash != token for t in stored)                         # only the hash is stored
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "weak"}).status_code == 422
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "Rec0veredPassword"}).status_code == 200
    assert client.post("/api/auth/reset-password", json={"token": token, "new_password": "An0therPassword"}).status_code == 400  # single use
    assert client.post("/api/auth/login", data={"username": "forgetful", "password": "Rec0veredPassword"}).status_code == 200


def test_new_reset_request_invalidates_previous_link(client, admin):
    reg(client, "twice")
    first = client.post("/api/auth/forgot-password", json={"email": "twice@example.com"}).json()["dev_reset_link"].split("token=")[1]
    client.post("/api/auth/forgot-password", json={"email": "twice@example.com"})
    assert client.post("/api/auth/reset-password", json={"token": first, "new_password": "Rec0veredPassword"}).status_code == 400


def test_admin_cannot_remove_last_admin_and_non_admins_cannot_manage_users(client, admin, analyst):
    users = client.get("/api/users", headers=admin).json()
    me = next(u for u in users if u["username"] == "gov_admin")
    assert client.patch(f"/api/users/{me['id']}", headers=admin, json={"app_role": "analyst"}).status_code == 409
    assert client.get("/api/users", headers=analyst).status_code == 403


def test_login_rate_limit(client, admin):
    codes = [client.post("/api/auth/login", data={"username": "gov_admin", "password": "nope"}).status_code for _ in range(22)]
    assert 429 in codes
