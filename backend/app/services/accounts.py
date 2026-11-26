"""Account management: registration rules, password policy, reset tokens, email delivery, rate limiting."""
from __future__ import annotations

import hashlib
import logging
import re
import secrets
import smtplib
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from email.message import EmailMessage

from fastapi import HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import PasswordResetToken, User

log = logging.getLogger("emea_guard.accounts")

USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,29}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
COMMON_PASSWORDS = {"password", "password1", "password123", "1234567890", "qwertyuiop", "letmein123", "welcome123", "admin12345"}


def normalise_email(email: str) -> str:
    return email.strip().lower()


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


def role_for_new_user(db: Session) -> str:
    """The first account becomes admin; everyone after that starts as analyst."""
    return "admin" if db.execute(select(func.count()).select_from(User)).scalar_one() == 0 else "analyst"


def find_user(db: Session, identifier: str) -> User | None:
    ident = identifier.strip()
    if "@" in ident:
        return db.execute(select(User).where(User.email == normalise_email(ident))).scalar_one_or_none()
    return db.execute(select(User).where(func.lower(User.username) == ident.lower())).scalar_one_or_none()


# ------------------------------------------------------------------ reset tokens
def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_reset_token(db: Session, user: User) -> str:
    now = datetime.utcnow()
    # invalidate any outstanding tokens for this user
    for t in db.execute(select(PasswordResetToken).where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))).scalars():
        t.used_at = now
    token = secrets.token_urlsafe(32)
    db.add(PasswordResetToken(user_id=user.id, token_hash=_hash_token(token), created_at=now,
                              expires_at=now + timedelta(minutes=get_settings().password_reset_minutes)))
    return token


def consume_reset_token(db: Session, token: str) -> User:
    row = db.execute(select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(token))).scalar_one_or_none()
    now = datetime.utcnow()
    if not row or row.used_at is not None or row.expires_at < now:
        raise HTTPException(400, "This reset link is invalid or has expired. Request a new one.")
    row.used_at = now
    return row.user


def reset_link(token: str) -> str:
    return f"{get_settings().app_base_url.rstrip('/')}/#/reset-password?token={token}"


def send_reset_email(to: str, username: str, link: str) -> bool:
    """Send the reset email via SMTP. Returns False when SMTP is not configured or fails."""
    s = get_settings()
    if not s.smtp_host:
        log.warning("SMTP not configured; password reset link for %s: %s", username, link)
        return False
    msg = EmailMessage()
    msg["Subject"] = "Reset your EMEA Guard password"
    msg["From"] = s.smtp_from
    msg["To"] = to
    msg.set_content(
        f"Hi {username},\n\nSomeone asked to reset the password for your EMEA Guard account.\n\n"
        f"Reset it here (the link works once and expires in {s.password_reset_minutes} minutes):\n{link}\n\n"
        "If you didn't ask for this, ignore this email and your password stays the same.\n"
    )
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            if s.smtp_starttls:
                smtp.starttls()
            if s.smtp_username:
                smtp.login(s.smtp_username, s.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception:  # noqa: BLE001 - never leak SMTP errors to the client
        log.exception("Failed to send password reset email")
        return False


# ------------------------------------------------------------------ rate limiting
class RateLimiter:
    """Sliding-window limiter per client IP and action (in-memory; per process)."""

    def __init__(self) -> None:
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, request: Request, action: str, limit: int, window_s: int) -> None:
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?")
        key, now = f"{action}:{ip}", time.monotonic()
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
