"""JWT authentication and role-based authorisation for platform users."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def _pwc(user) -> int:
    """Password-change marker embedded in tokens, so changing a password signs out other sessions."""
    return getattr(user, "token_version", 0) or 0


def create_access_token(user) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expiry_minutes)
    return jwt.encode({"sub": user.username, "role": user.app_role, "pwc": _pwc(user), "exp": exp}, s.jwt_secret, algorithm=s.jwt_algorithm)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    from .models import User

    s = get_settings()
    cred_exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token",
                             headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
        username = payload.get("sub")
    except JWTError as err:
        raise cred_exc from err
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None or not user.is_active or payload.get("pwc", 0) != _pwc(user):
        raise cred_exc
    return user


def require_roles(*roles: str):
    def checker(user=Depends(get_current_user)):
        if user.app_role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Requires role: {', '.join(roles)}")
        return user
    return checker


can_write = require_roles("admin", "analyst")
admin_only = require_roles("admin")
