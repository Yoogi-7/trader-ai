# apps/api/security.py
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.api.config import settings
from apps.api.db import models
from apps.api.db.session import SessionLocal

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
http_bearer = HTTPBearer(auto_error=False)


def get_db_session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_password(plain_password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    return pwd_context.verify(plain_password, password_hash)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: Dict[str, Any], expires_minutes: int | None = None) -> str:
    expire_delta = expires_minutes or settings.jwt_exp_minutes
    expire = datetime.now(tz=timezone.utc) + timedelta(minutes=expire_delta)
    payload = subject.copy()
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    db: Session = Depends(get_db_session),
) -> models.User:
    if credentials is None or not credentials.scheme.lower() == "bearer":
        if settings.auth_auto_admin:
            return _autologin_admin(db)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = db.get(models.User, int(user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def ensure_default_admin(db: Session) -> None:
    email = settings.admin_email.strip().lower()
    if not email:
        return
    existing = db.query(models.User).filter(models.User.email == email).first()
    if existing:
        return
    now_ms = int(time.time() * 1000)
    user = models.User(
        email=email,
        password_hash=get_password_hash(settings.admin_password),
        role="ADMIN",
        created_at=now_ms,
        updated_at=now_ms,
        risk_profile="LOW",
        capital=100.0,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def _autologin_admin(db: Session) -> models.User:
    ensure_default_admin(db)
    normalized_email = settings.admin_email.strip().lower()
    if normalized_email:
        admin = db.query(models.User).filter(models.User.email == normalized_email).first()
        if admin is not None:
            return admin
    admin = (
        db.query(models.User)
        .filter(models.User.role == "ADMIN")
        .order_by(models.User.id)
        .first()
    )
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin account not available")
    return admin
