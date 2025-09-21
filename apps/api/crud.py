# apps/api/crud.py
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select, update, insert
from apps.api.db import models

def get_user(db: Session, user_id: int = 1):
    return db.execute(select(models.User).where(models.User.id == user_id)).scalar_one_or_none()

def upsert_user_settings(db: Session, user_id: int, risk_profile: str, prefs: Optional[Dict[str, Any]], margin_mode: Optional[str] = None):
    user = get_user(db, user_id)
    if user is None:
        db.execute(insert(models.User).values(
            id=user_id, risk_profile=risk_profile, capital=100.0, prefs=prefs or {}, api_connected=False
        ))
    else:
        upd = {"risk_profile": risk_profile}
        if prefs is not None:
            upd["prefs"] = prefs
        if margin_mode:
            # zapis w prefs dla spójności
            new_prefs = dict(user.prefs or {})
            new_prefs["margin_mode"] = margin_mode
            upd["prefs"] = new_prefs
        db.execute(update(models.User).where(models.User.id == user_id).values(**upd))

def update_capital(db: Session, user_id: int, capital: float):
    user = get_user(db, user_id)
    if user is None:
        db.execute(insert(models.User).values(
            id=user_id, risk_profile="LOW", capital=capital, prefs={}, api_connected=False
        ))
    else:
        db.execute(update(models.User).where(models.User.id == user_id).values(capital=capital))
