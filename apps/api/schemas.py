
from pydantic import BaseModel, Field
from typing import List, Optional

class StartBackfillRequest(BaseModel):
    pairs: List[str]
    tf: str = "1m"

class StartTrainRequest(BaseModel):
    params: dict = Field(default_factory=dict)

class StartBacktestRequest(BaseModel):
    params: dict = Field(default_factory=dict)

class SignalDTO(BaseModel):
    id: str
    symbol: str
    tf_base: str
    ts: int
    dir: str
    entry: float
    tp: list[float]
    sl: float
    lev: int
    risk: float
    margin_mode: str
    expected_net_pct: float
    confidence: float
    model_ver: str
    reason_discard: str | None = None
    status: str
