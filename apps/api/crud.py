
from sqlalchemy.orm import Session
from apps.api.db import models
from typing import List

def save_signal(db: Session, sig: models.Signal):
    db.add(sig)
    db.commit()

def list_signals(db: Session, limit: int = 50) -> List[models.Signal]:
    return db.query(models.Signal).order_by(models.Signal.ts.desc()).limit(limit).all()
