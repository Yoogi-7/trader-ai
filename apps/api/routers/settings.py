from fastapi import APIRouter
from pydantic import BaseModel
from apps.api.config import settings

router = APIRouter()


class SystemSettings(BaseModel):
    min_confidence_threshold: float
    min_net_profit_pct: float
    maker_fee_bps: float
    taker_fee_bps: float
    slippage_bps: float


@router.get("/", response_model=SystemSettings)
async def get_settings():
    """Get system settings"""
    return SystemSettings(
        min_confidence_threshold=settings.MIN_CONFIDENCE_THRESHOLD,
        min_net_profit_pct=settings.MIN_NET_PROFIT_PCT,
        maker_fee_bps=settings.MAKER_FEE_BPS,
        taker_fee_bps=settings.TAKER_FEE_BPS,
        slippage_bps=settings.SLIPPAGE_BPS
    )
