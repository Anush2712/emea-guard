"""Account management: registration rules, password policy, reset tokens, email delivery, rate limiting."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import smtplib
import threading
import time
import urllib.request
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from ipaddress import ip_address

from fastapi import HTTPException, Request
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import PasswordResetToken, User

log = logging.getLogger("emea_guard.accounts")

USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,29}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
COMMON_PASSWORDS = {"password", "password1", "password123", "1234567890", "qwertyuiop", "letmein123", "welcome123", "admin12345"}

# Serialises the "first account becomes admin" and "keep one active admin" checks inside one process.
# PostgreSQL deployments additionally take a transaction-scoped advisory lock / row locks (see below),
# so the checks also hold across several API processes.
account_lock = threading.Lock()
ADVISORY_LOCK_KEY = 72_712_001


def utcnow() -> datetime:
    """Naive UTC timestamp (the database columns are naive), without the deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalise_email(email: str) -> str:
    return email.strip().lower()


def username_key(username: str) -> str:
    return username.strip().lower()


def validate_username(username: str) -> str:
    if not USERNAME_RE.match(username):
        raise HTTPException(422, "Username must be 3-30 characters: letters, numbers, dot, dash or underscore, starting with a letter or number.")
    return username


def validate_email(email: str) -> str:
    email = normalise_email(email)
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise HTTPException(422, "Enter a valid email address.")
    return email


def password_problems(password: str, username: str = "") -> list[str]:
    problems = []
    if len(password) < 10:
        problems.append("at least 10 characters")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        problems.append("at least one letter and one number")
    if password.lower() in COMMON_PASSWORDS or (username and username.lower() in password.lower()):
        problems.append("not a common password or your username")
    if len(password) > 128:
        problems.append("no more than 128 characters")
    return problems


def validate_password(password: str, username: str = "") -> None:
    problems = password_problems(password, username)
    if problems:
        raise HTTPException(422, "Password needs " + ", ".join(problems) + ".")


def lock_accounts_table(db: Session) -> None:
    """Transaction-scoped advisory lock on PostgreSQL (released at commit/rollback); no-op elsewhere."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": ADVISORY_LOCK_KEY})


def role_for_new_user(db: Session) -> str:
    """The first account becomes admin; everyone after that starts as analyst. Call under the account lock."""
    return "admin" if db.execute(select(func.count()).select_from(User)).scalar_one() == 0 else "analyst"


def find_user(db: Session, identifier: str) -> User | None:
    ident = identifier.strip()
    if "@" in ident:
        return db.execute(select(User).where(User.email == normalise_email(ident))).scalar_one_or_none()
    return db.execute(select(User).where(User.username_key == username_key(ident))).scalar_one_or_none()


def active_admin_count_locked(db: Session) -> int:
    """Count active admins while holding row locks on them (ordered by id to avoid deadlocks)."""
    rows = db.execute(
        select(User.id).where(User.app_role == "admin", User.is_active.is_(True)).order_by(User.id).with_for_update()
    ).all()
    return len(rows)


# ------------------------------------------------------------------ reset tokens
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_reset_token(db: Session, user: User) -> str:
    now = utcnow()
    db.execute(update(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None)).values(used_at=now))
    token = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(user_id=user.id, token_hash=_hash_token(token), created_at=now,
                              expires_at=now + timedelta(minutes=get_settings().password_reset_minutes)))
    return token


INVALID_LINK = "This reset link is invalid or has expired. Request a new one."


def peek_reset_token(db: Session, token: str) -> User:
    """Look up the account for a token without using it (so the new password can be validated first)."""
    row = db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(token))).scalar_one_or_none()
    if not row or row.used_at is not None or row.expires_at < utcnow():
        raise HTTPException(400, INVALID_LINK)
    return row.user


def consume_reset_token(db: Session, token: str) -> int:
    """Atomically mark the token used. Exactly one concurrent caller can succeed; returns the user id."""
    now = utcnow()
    h = _hash_token(token)
    result = db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.token_hash == h, PasswordResetToken.used_at.is_(None), PasswordResetToken.expires_at >= now)
        .values(used_at=now)
    )
    if result.rowcount != 1:
        raise HTTPException(400, INVALID_LINK)
    return db.execute(select(PasswordResetToken.user_id).where(PasswordResetToken.token_hash == h)).scalar_one()


def reset_link(token: str) -> str:
    return f"{get_settings().app_base_url.rstrip('/')}/#/reset-password?token={token}"


def _email_body(username: str, link: str) -> str:
    return (
        f"Hi {username},\n\nSomeone asked to reset the password for your EMEA Guard account.\n\n"
        f"Reset it here (the link works once and expires in {get_settings().password_reset_minutes} minutes):\n{link}\n\n"
        "If you didn't ask for this, ignore this email and your password stays the same.\n"
    )


def send_reset_email(to: str, username: str, link: str) -> bool:
    """Deliver the reset link: Resend HTTPS API, else SMTP, else (development only) the server log.

    The raw link is never logged outside development, so log access cannot be used to take over accounts.
    """
    s = get_settings()
    subject = "Reset your EMEA Guard password"
    try:
        if s.resend_api_key:  # HTTPS (port 443): works on hosts that block outbound SMTP, e.g. Render's free tier
            req = urllib.request.Request(
                "https://api.resend.com/emails", method="POST",
                data=json.dumps({"from": s.smtp_from, "to": [to], "subject": subject, "text": _email_body(username, link)}).encode(),
                headers={"Authorization": f"Bearer {s.resend_api_key}", "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310 - fixed https URL
                return 200 <= resp.status < 300
        if s.smtp_host:
            msg = EmailMessage()
            msg["Subject"], msg["From"], msg["To"] = subject, s.smtp_from, to
            msg.set_content(_email_body(username, link))
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
                if s.smtp_starttls:
                    smtp.starttls()
                if s.smtp_username:
                    smtp.login(s.smtp_username, s.smtp_password)
                smtp.send_message(msg)
            return True
    except Exception:  # noqa: BLE001 - never leak delivery errors to the client
        log.exception("Failed to send password reset email for %s", username)
        return False
    if s.is_development:
        log.warning("No email delivery configured (development): password reset link for %s: %s", username, link)
    else:
        log.error("Password reset requested for %s but no email delivery is configured; link not sent or logged.", username)
    return False


# ------------------------------------------------------------------ rate limiting
def client_ip(request: Request) -> str:
    """Client address for rate limiting.

    Only configured immediate proxy peers can supply X-Forwarded-For. The configured
    hop count selects the address from the right of the trusted proxy chain.
    """
    settings = get_settings()
    hops = settings.trusted_proxy_hops
    peer = request.client.host if request.client else "?"
    if hops <= 0 or not settings.trusted_proxy_networks:
        return peer
    try:
        if not any(ip_address(peer) in network for network in settings.trusted_proxy_networks):
            return peer
        parts = [part.strip() for value in request.headers.getlist("x-forwarded-for") for part in value.split(",")]
        if len(parts) >= hops:
            return str(ip_address(parts[-hops]))
    except ValueError:
        pass
    return peer


class RateLimiter:
    """Sliding-window limiter per client IP and action (in-memory; per process)."""

    def __init__(self) -> None:
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, request: Request, action: str, limit: int, window_s: int) -> None:
        key, now = f"{action}:{client_ip(request)}", time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > window_s:
                q.popleft()
            if len(q) >= limit:
                raise HTTPException(429, f"Too many attempts. Try again in {int(window_s - (now - q[0])) + 1} seconds.")
            q.append(now)

    def reset(self) -> None:
        with self.lock:
            self.hits.clear()


limiter = RateLimiter()
