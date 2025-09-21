from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class BackfillStart(BaseModel):
    pairs: Optional[List[str]] = None
    tf: str = "1m"
    since_ms: Optional[int] = None

class TrainRun(BaseModel):
    params: Dict = {}

class BacktestRun(BaseModel):
    params: Dict = {}

class SignalRequest(BaseModel):
    pairs: List[str]
    risk_profile: str = "LOW"
    capital: float = 100.0

class SignalOut(BaseModel):
    id: int; symbol: str; dir: str; entry: float; sl: float
    tp: List[float]; lev: int; risk: float
    margin_mode: str; expected_net_pct: float; confidence: float
    status: str; reason_discard: Optional[str] = None