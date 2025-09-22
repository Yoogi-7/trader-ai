
from pydantic import BaseModel, Field, condecimal, validator
from typing import Optional, List, Literal, Dict
from datetime import datetime

RiskProfile = Literal["LOW", "MED", "HIGH"]

class UserSettingsIn(BaseModel):
    risk_profile: RiskProfile = Field(..., description="LOW/MED/HIGH")
    pairs: Optional[List[str]] = Field(default=None, description="Whitelist symboli, np. ['BTCUSDT','ETHUSDT']")
    max_parallel_positions: Optional[int] = Field(default=None, ge=1, le=50)
    margin_mode: Optional[Literal["isolated", "cross"]] = "isolated"

class CapitalIn(BaseModel):
    capital: condecimal(gt=0, decimal_places=2) = Field(..., description="Kapitał użytkownika w USD")

class UserOut(BaseModel):
    id: int
    risk_profile: RiskProfile
    capital: float
    prefs: Optional[Dict] = None
    api_connected: bool

class BackfillStartRequest(BaseModel):
    symbols: List[str]
    tf: str = "1m"
    years: int = 4

class TrainRunRequest(BaseModel):
    params: dict = Field(default_factory=dict)

class BacktestRequest(BaseModel):
    capital: float = 100.0
    risk_profile: RiskProfile = "LOW"
    pairs: List[str]
    fee_maker_bps: float = 7.0
    fee_taker_bps: float = 10.0
    slippage_bps: float = 5.0
    funding_on: bool = True

class SignalPublishRequest(BaseModel):
    symbol: str
    direction: Literal["LONG","SHORT"]
    entry: float
    sl: float
    tp: List[float]
    leverage: int
    risk_pct: float
    margin_mode: Literal["isolated","cross"]
    tf_base: str = "15m"
    ts: datetime
    confidence: Optional[float] = None
