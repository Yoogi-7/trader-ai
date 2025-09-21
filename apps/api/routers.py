# apps/api/routers.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, Dict

from apps.api.db.session import get_db
from apps.api.schemas import UserSettingsIn, CapitalIn, UserOut
from apps.api import crud
from apps.api.services.risk import map_profile

router = APIRouter()

@router.get("/health", tags=["system"])
def health() -> Dict[str, Any]:
    return {"status": "ok"}

@router.post("/settings/profile", response_model=UserOut, tags=["settings"])
def set_profile(payload: UserSettingsIn, db: Session = Depends(get_db)) -> UserOut:
    # mapowanie profilu na parametry (aby zweryfikować, że profil istnieje)
    params = map_profile(payload.risk_profile)

    # prefs: zapisujemy pairs, max_parallel_positions override oraz margin_mode
    prefs = {}
    if payload.pairs is not None:
        prefs["pairs"] = payload.pairs
    if payload.max_parallel_positions is not None:
        # pozwalamy nadpisać w dół, ale nie w górę
        if payload.max_parallel_positions > params.max_parallel_positions:
            raise HTTPException(status_code=400, detail=f"max_parallel_positions cannot exceed preset ({params.max_parallel_positions})")
        prefs["max_parallel_positions_override"] = payload.max_parallel_positions
    if payload.margin_mode:
        prefs["margin_mode"] = payload.margin_mode

    crud.upsert_user_settings(db, user_id=1, risk_profile=payload.risk_profile, prefs=prefs or None, margin_mode=payload.margin_mode)
    db.commit()
    user = crud.get_user(db, 1)
    if not user:
        raise HTTPException(status_code=500, detail="user_not_persisted")
    return UserOut(
        id=user.id,
        risk_profile=user.risk_profile,
        capital=float(user.capital or 0),
        prefs=user.prefs or {},
        api_connected=bool(user.api_connected),
    )

@router.post("/capital", response_model=UserOut, tags=["settings"])
def set_capital(payload: CapitalIn, db: Session = Depends(get_db)) -> UserOut:
    crud.update_capital(db, user_id=1, capital=float(payload.capital))
    db.commit()
    user = crud.get_user(db, 1)
    if not user:
        raise HTTPException(status_code=500, detail="user_not_persisted")
    return UserOut(
        id=user.id,
        risk_profile=user.risk_profile,
        capital=float(user.capital or 0),
        prefs=user.prefs or {},
        api_connected=bool(user.api_connected),
    )

# PRZYKŁADOWE endpointy z istniejącego zakresu (zostaw jeśli już masz):
@router.get("/signals/live", tags=["signals"])
def signals_live_demo() -> Dict[str, Any]:
    # stub – docelowo WS
    return {"live": True, "items": []}
