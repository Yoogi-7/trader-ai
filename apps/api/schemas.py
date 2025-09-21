# apps/api/schemas.py
from pydantic import BaseModel, Field, condecimal, validator
from typing import Optional, List, Literal, Dict

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
