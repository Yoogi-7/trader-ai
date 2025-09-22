
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Dict, Any
from apps.api.db.models import User

def get_or_create_user(db: Session) -> User:
    obj = db.execute(select(User).limit(1)).scalar_one_or_none()
    if obj is None:
        obj = User()
        db.add(obj)
        db.commit()
        db.refresh(obj)
    return obj

def update_user(db: Session, payload: Dict[str, Any]) -> User:
    user = get_or_create_user(db)
    for k,v in payload.items():
        setattr(user, k, v)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
