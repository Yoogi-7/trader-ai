# apps/api/routes/settings.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from apps.api.deps import db_dep
from apps.api import schemas, crud

router = APIRouter(prefix="/settings", tags=["settings"])

@router.post("/profile", response_model=schemas.OkResp)
def set_profile(req: schemas.UserSettingsReq, db: Session = Depends(db_dep)):
    ok = crud.user_upsert_settings(db, req.user_id, req.risk_profile, req.capital, req.prefs)
    return schemas.OkResp(ok=ok)

@router.post("/capital", response_model=schemas.OkResp)
def set_capital(req: schemas.UserCapitalReq, db: Session = Depends(db_dep)):
    ok = crud.user_set_capital(db, req.user_id, req.capital)
    return schemas.OkResp(ok=ok)
