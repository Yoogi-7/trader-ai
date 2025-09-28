# apps/api/schemas.py
# PL: Schematy Pydantic do API. EN: Pydantic schemas for API.

from pydantic import BaseModel, Field, conlist, validator, ConfigDict
from typing import Optional, List, Literal, Any, Dict

# -------- Backfill --------

# -------- Auth / Users --------

class AuthLoginReq(BaseModel):
    email: str
    password: str

class UserInfo(BaseModel):
    id: int
    email: str
    role: Literal['ADMIN', 'USER']
    risk_profile: str
    capital: float
    prefs: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    user: UserInfo

class UserCreateReq(BaseModel):
    email: str
    password: str
    role: Literal['ADMIN', 'USER'] = 'USER'
    risk_profile: Literal['LOW', 'MED', 'HIGH'] = 'LOW'
    capital: float = 100.0
    prefs: Dict[str, Any] | None = None

class UserUpdateReq(BaseModel):
    role: Literal['ADMIN', 'USER'] | None = None
    password: Optional[str] = None
    risk_profile: Literal['LOW', 'MED', 'HIGH'] | None = None
    capital: Optional[float] = None
    prefs: Optional[Dict[str, Any]] = None

class BackfillStartReq(BaseModel):
    symbols: conlist(str, min_length=1)
    tf: Literal["1m", "5m", "15m", "1h", "4h", "1d"] = "15m"
    from_ts: Optional[int] = None  # epoch ms
    to_ts: Optional[int] = None    # epoch ms

class BackfillItem(BaseModel):
    id: int
    symbol: str
    tf: str
    last_ts_completed: Optional[int]
    chunk_start_ts: Optional[int]
    chunk_end_ts: Optional[int]
    retry_count: int
    status: str
    updated_at: int

class BackfillStartResp(BaseModel):
    created: int
    items: List[BackfillItem]

class BackfillStatusResp(BaseModel):
    total: int
    items: List[BackfillItem]

# -------- Train --------

class TrainRunReq(BaseModel):
    params: Dict[str, Any] = Field(default_factory=dict)

class TrainRunItem(BaseModel):
    id: int
    started_at: int
    finished_at: Optional[int]
    status: str
    params_json: Optional[Dict[str, Any]]
    metrics_json: Optional[Dict[str, Any]]

class TrainRunResp(BaseModel):
    created_id: int

class TrainStatusResp(BaseModel):
    total: int
    items: List[TrainRunItem]

# -------- Backtest --------

class BacktestRunReq(BaseModel):
    params: Dict[str, Any] = Field(default_factory=dict)

class BacktestItem(BaseModel):
    id: int
    started_at: int
    finished_at: Optional[int]
    summary_json: Optional[Dict[str, Any]]

class BacktestRunResp(BaseModel):
    created_id: int

class BacktestResultsResp(BaseModel):
    total: int
    items: List[BacktestItem]

# -------- Signals --------

class SignalCreateReq(BaseModel):
    symbol: str
    tf_base: Literal["15m", "1h", "4h"]
    ts: int
    dir: Literal["LONG", "SHORT"]
    entry: float
    tp: Optional[List[float]] = None
    sl: float
    lev: float = Field(ge=1)
    risk: Literal["LOW", "MED", "HIGH"] = "LOW"
    margin_mode: Literal["ISOLATED", "CROSS"] = "ISOLATED"
    expected_net_pct: float = Field(..., description=">= 0.02 means 2% net")
    confidence: Optional[float] = None
    model_ver: Optional[str] = None
    reason_discard: Optional[str] = None
    ai_summary: Optional[str] = None

    @validator("expected_net_pct")
    def validate_net(cls, v):
        if v < 0:
            raise ValueError("expected_net_pct must be >= 0")
        return v

class SignalItem(BaseModel):
    id: str
    symbol: str
    tf_base: str
    ts: int
    dir: str
    entry: float
    tp: Optional[List[float]]
    sl: float
    lev: float
    risk: str
    margin_mode: str
    expected_net_pct: float
    confidence: Optional[float] = None
    confidence_rating: Optional[int] = None
    market_regime: Optional[str] = None
    sentiment_rating: Optional[int] = None
    model_ver: Optional[str] = None
    reason_discard: Optional[str] = None
    status: str
    ai_summary: Optional[str] = None

class SignalsListResp(BaseModel):
    total: int
    items: List[SignalItem]


# -------- Leaderboard --------

class LeaderboardOverall(BaseModel):
    win_rate: float
    total_trades: int
    wins: int
    period_start_ms: int
    period_end_ms: int


class LeaderboardUserEntry(BaseModel):
    rank: int
    user_id: int
    email: str
    capital: float
    risk_profile: str


class LeaderboardResp(BaseModel):
    overall: LeaderboardOverall
    users: List[LeaderboardUserEntry]

# -------- Risk Dashboard --------

class RiskMetricsBlock(BaseModel):
    source: Literal["backtest", "live"]
    max_drawdown: Optional[float]
    max_drawdown_pct: Optional[float]
    avg_profit_per_trade: Optional[float]
    win_rate: Optional[float]
    trades: int
    pnl_total: Optional[float]
    capital: Optional[float]
    last_updated_ms: Optional[int]


class RiskDashboardResp(BaseModel):
    backtest: RiskMetricsBlock
    live: RiskMetricsBlock

# -------- Arbitrage --------

class ArbitrageScanReq(BaseModel):
    symbols: List[str]
    exchanges: List[str]
    min_spread_pct: float = Field(0.3, ge=0.0)
    market_type: Literal["spot", "future"] = "spot"


class ArbitrageOpportunity(BaseModel):
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    spread_pct: float
    timestamp_ms: int


class ArbitrageScanResp(BaseModel):
    opportunities: List[ArbitrageOpportunity]

# -------- Settings / Users --------

class UserSettingsReq(BaseModel):
    user_id: Optional[int] = None
    risk_profile: Literal["LOW", "MED", "HIGH"] = "LOW"
    capital: float = Field(gt=0, default=100.0)
    prefs: Dict[str, Any] = Field(default_factory=dict)

class UserCapitalReq(BaseModel):
    user_id: int
    capital: float = Field(gt=0)

class OkResp(BaseModel):
    ok: bool


# -------- Trading Journal --------

class JournalEquityPoint(BaseModel):
    ts: int
    equity: float


class JournalTradeRef(BaseModel):
    symbol: str
    ts: int
    pnl: float
    direction: str
    market_regime: Optional[str] = None
    sentiment_rating: Optional[int] = None
    ai_summary: Optional[str] = None


class JournalMetrics(BaseModel):
    total_trades: int
    win_rate: float
    avg_pnl: float
    max_drawdown: float
    cumulative_pnl: float
    best_trade: Optional[JournalTradeRef]
    worst_trade: Optional[JournalTradeRef]


class JournalRegimeEntry(BaseModel):
    regime: str
    trades: int
    win_rate: float
    pnl: float


class JournalSentimentSummary(BaseModel):
    avg_rating: Optional[float]
    positive_share: Optional[float]
    negative_share: Optional[float]


class TradingJournalResp(BaseModel):
    equity_curve: List[JournalEquityPoint]
    metrics: JournalMetrics
    recent_mistakes: List[JournalTradeRef]
    regime_breakdown: List[JournalRegimeEntry]
    sentiment_summary: JournalSentimentSummary
