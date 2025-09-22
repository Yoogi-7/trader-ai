from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class BackfillStartRequest(BaseModel):
    symbols: List[str]
    tf: str = "1m"
    years: int = 4

class TrainRunRequest(BaseModel):
    params: dict = Field(default_factory=dict)

class BacktestRequest(BaseModel):
    capital: float = 100.0
    risk_profile: str = "LOW"
    pairs: List[str]
    fee_maker_bps: float = 7
    fee_taker_bps: float = 10
    slippage_bps: float = 5
    funding_on: bool = True

class SignalPublishRequest(BaseModel):
    symbol: str
    dir: str
    entry: float
    sl: float
    tp: list[float]
    lev: float
    risk: float
    margin_mode: str
    tf_base: str = "15m"
    ts: datetime
    confidence: Optional[float] = None
