"""Sign-up, login, password change, email password reset and user administration."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import admin_only, create_access_token, get_current_user, hash_password, verify_password
from ..config import get_settings
from ..database import get_db
from ..models import User
from ..schemas import Token
from ..services import accounts as A
from ..services.audit import AuditTrail

router = APIRouter(tags=["accounts"])


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)
    full_name: str | None = Field(default=None, max_length=100)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


class ForgotIn(BaseModel):
    email: str


class ResetIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str


class RoleIn(BaseModel):
    app_role: str | None = None
    is_active: bool | None = None


def user_dict(u: User) -> dict:
    return {"id": u.id, "username": u.username, "email": u.email, "full_name": u.full_name, "role": u.app_role,
            "is_active": u.is_active, "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None}


def _token(u: User) -> Token:
    return Token(access_token=create_access_token(u), role=u.app_role, full_name=u.full_name, username=u.username)


@router.post("/auth/register", response_model=Token, status_code=201, summary="Create an account (first account becomes admin)")
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    A.limiter.check(request, "register", limit=10, window_s=3600)
    username = A.validate_username(body.username.strip())
    email = A.validate_email(body.email)
    A.validate_password(body.password, username)
    if db.execute(select(User).where(func.lower(User.username) == username.lower())).scalar_one_or_none():
        raise HTTPException(409, "That username is taken. Choose another.")
    if db.execute(select(User).where(User.email == email)).scalar_one_or_none():
        raise HTTPException(409, "An account with that email already exists. Sign in or reset your password.")
    now = datetime.utcnow()
    u = User(username=username, email=email, full_name=(body.full_name or username).strip(), hashed_password=hash_password(body.password),
             app_role=A.role_for_new_user(db), is_active=True, token_version=0, created_at=now, last_login_at=now, password_changed_at=now)
    db.add(u)
    db.flush()
    AuditTrail(db).record(actor=u.username, action="USER_REGISTERED", entity_type="User", entity_id=u.username, details={"role": u.app_role})
    db.commit()
    return _token(u)


@router.post("/auth/login", response_model=Token, summary="Sign in with username or email")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    A.limiter.check(request, "login", limit=20, window_s=300)
    u = A.find_user(db, form.username)
    if not u or not verify_password(form.password, u.hashed_password):
        raise HTTPException(401, "Incorrect username or password.")
    if not u.is_active:
        raise HTTPException(403, "This account is disabled. Ask an administrator to re-enable it.")
    u.last_login_at = datetime.utcnow()
    AuditTrail(db).record(actor=u.username, action="USER_LOGIN", entity_type="User", entity_id=u.username)
    db.commit()
    return _token(u)


@router.get("/auth/me")
def me(user: User = Depends(get_current_user)):
    return user_dict(user)


@router.post("/auth/change-password", summary="Change your password (requires the current one)")
def change_password(body: ChangePasswordIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    A.limiter.check(request, "change-password", limit=10, window_s=300)
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(400, "Your current password is incorrect.")
    A.validate_password(body.new_password, user.username)
    if verify_password(body.new_password, user.hashed_password):
        raise HTTPException(422, "Choose a password different from your current one.")
    u = db.get(User, user.id)
    u.hashed_password, u.password_changed_at = hash_password(body.new_password), datetime.utcnow()
    u.token_version = (u.token_version or 0) + 1
    AuditTrail(db).record(actor=u.username, action="PASSWORD_CHANGED", entity_type="User", entity_id=u.username)
    db.commit()
    return {"message": "Password changed. Other signed-in sessions have been signed out.", **_token(u).model_dump()}


@router.post("/auth/forgot-password", summary="Email a single-use password reset link")
def forgot_password(body: ForgotIn, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    A.limiter.check(request, "forgot", limit=5, window_s=900)
    generic = {"message": "If an account uses that email, a reset link is on its way. It expires in "
                          f"{get_settings().password_reset_minutes} minutes."}
    email = A.normalise_email(body.email)
    u = db.execute(select(User).where(User.email == email, User.is_active.is_(True))).scalar_one_or_none()
    if not u:
        return generic  # never reveal whether an email is registered
    token = A.create_reset_token(db, u)
    AuditTrail(db).record(actor=u.username, action="PASSWORD_RESET_REQUESTED", entity_type="User", entity_id=u.username)
    db.commit()
    link = A.reset_link(token)
    s = get_settings()
    if s.smtp_host:
        background.add_task(A.send_reset_email, u.email, u.username, link)
        return generic
    A.send_reset_email(u.email, u.username, link)  # logs the link
    if not s.is_production:
        return {**generic, "dev_reset_link": link, "note": "SMTP is not configured, so the link is shown here (development only)."}
    return generic


@router.post("/auth/reset-password", summary="Set a new password with a reset token")
def reset_password(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    A.limiter.check(request, "reset", limit=10, window_s=900)
    u = A.consume_reset_token(db, body.token)
    A.validate_password(body.new_password, u.username)
    u.hashed_password, u.password_changed_at = hash_password(body.new_password), datetime.utcnow()
    u.token_version = (u.token_version or 0) + 1
    AuditTrail(db).record(actor=u.username, action="PASSWORD_RESET", entity_type="User", entity_id=u.username)
    db.commit()
    return {"message": "Password updated. Sign in with your new password."}


@router.get("/users", summary="List accounts (admin)")
def list_users(db: Session = Depends(get_db), _=Depends(admin_only)):
    return [user_dict(u) for u in db.execute(select(User).order_by(User.created_at)).scalars()]


@router.patch("/users/{user_id}", summary="Change a user's role or disable the account (admin)")
def update_user(user_id: int, body: RoleIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "Not found")
    if body.app_role is not None and body.app_role not in ("admin", "analyst", "auditor"):
        raise HTTPException(422, "Role must be admin, analyst or auditor.")
    demoting = (body.app_role and body.app_role != "admin") or body.is_active is False
    if u.app_role == "admin" and demoting:
        admins = db.execute(select(func.count()).select_from(User).where(User.app_role == "admin", User.is_active.is_(True))).scalar_one()
        if admins <= 1:
            raise HTTPException(409, "There must always be at least one active admin.")
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(u, k, v)
    AuditTrail(db).record(actor=admin.username, action="USER_UPDATED", entity_type="User", entity_id=u.username, details=changes)
    db.commit()
    return user_dict(u)
