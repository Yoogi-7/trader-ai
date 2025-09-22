from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..db import SessionLocal
from ..models import Signal
from ..schemas import SignalPublishRequest
from ..services.filters import net_pct_after_costs, should_publish_signal
from ..config import settings

router = APIRouter(prefix="/signals", tags=["signals"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/generate")
def publish_signal(req: SignalPublishRequest, db: Session = Depends(get_db)):
    # policz expected_net_pct
    funding_bps = 1.0 if req.dir.upper()=="LONG" else 1.2  # przyklad
    expected = net_pct_after_costs(
        req.dir.upper(), req.entry, req.tp[0], req.sl, req.lev,
        fee_maker_bps=7, slippage_bps=5, funding_bps=funding_bps
    )
    ok, reason = should_publish_signal(expected, settings.MIN_NET_PCT, req.confidence, settings.CONFIDENCE_THRESHOLD)
    if not ok:
        s = Signal(symbol=req.symbol, tf_base=req.tf_base, ts=req.ts, dir=req.dir.upper(),
                   entry=req.entry, tp1=req.tp[0], tp2=(req.tp[1] if len(req.tp)>1 else None),
                   tp3=(req.tp[2] if len(req.tp)>2 else None),
                   sl=req.sl, lev=req.lev, risk=req.risk, margin_mode=req.margin_mode,
                   expected_net_pct=expected, confidence=req.confidence,
                   reason_discard=reason, status="discarded")
        db.add(s); db.commit()
        return {"published": False, "reason": reason, "expected_net_pct": expected}
    s = Signal(symbol=req.symbol, tf_base=req.tf_base, ts=req.ts, dir=req.dir.upper(),
               entry=req.entry, tp1=req.tp[0], tp2=(req.tp[1] if len(req.tp)>1 else None),
               tp3=(req.tp[2] if len(req.tp)>2 else None),
               sl=req.sl, lev=req.lev, risk=req.risk, margin_mode=req.margin_mode,
               expected_net_pct=expected, confidence=req.confidence,
               status="published")
    db.add(s); db.commit()
    return {"published": True, "expected_net_pct": expected, "signal_id": s.id}
