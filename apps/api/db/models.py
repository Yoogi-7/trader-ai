from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint, Index, JSON
)
from sqlalchemy.orm import relationship
from apps.api.db.base import Base


class TimeFrame(str, PyEnum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class RiskProfile(str, PyEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SignalStatus(str, PyEnum):
    PENDING = "pending"
    ACTIVE = "active"
    TP1_HIT = "tp1_hit"
    TP2_HIT = "tp2_hit"
    TP3_HIT = "tp3_hit"
    SL_HIT = "sl_hit"
    TIME_STOP = "time_stop"
    CANCELLED = "cancelled"


class Side(str, PyEnum):
    LONG = "long"
    SHORT = "short"


# ============================================================================
# MARKET DATA
# ============================================================================

class OHLCV(Base):
    __tablename__ = "ohlcv"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_ohlcv_symbol_tf_ts"),
        Index("idx_ohlcv_symbol_tf_ts", "symbol", "timeframe", "timestamp"),
        Index("idx_ohlcv_ts", "timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(Enum(TimeFrame), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class MarketMetrics(Base):
    __tablename__ = "market_metrics"
    __table_args__ = (
        UniqueConstraint("symbol", "timestamp", name="uq_market_metrics_symbol_ts"),
        Index("idx_market_metrics_symbol_ts", "symbol", "timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False)
    funding_rate = Column(Float)
    open_interest = Column(Float)
    spread_bps = Column(Float)
    depth_imbalance = Column(Float)
    realized_volatility = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# FEATURES & LABELS
# ============================================================================

class FeatureSet(Base):
    __tablename__ = "feature_sets"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_features_symbol_tf_ts"),
        Index("idx_features_symbol_tf_ts", "symbol", "timeframe", "timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(Enum(TimeFrame), nullable=False)
    timestamp = Column(DateTime, nullable=False)

    # Technical indicators
    ema_9 = Column(Float)
    ema_21 = Column(Float)
    ema_50 = Column(Float)
    ema_200 = Column(Float)
    rsi_14 = Column(Float)
    stoch_k = Column(Float)
    stoch_d = Column(Float)
    macd = Column(Float)
    macd_signal = Column(Float)
    macd_hist = Column(Float)
    atr_14 = Column(Float)
    bb_upper = Column(Float)
    bb_middle = Column(Float)
    bb_lower = Column(Float)
    bb_width = Column(Float)

    # Ichimoku
    tenkan_sen = Column(Float)
    kijun_sen = Column(Float)
    senkou_a = Column(Float)
    senkou_b = Column(Float)
    chikou_span = Column(Float)

    # Fibonacci & Pivots
    fib_618 = Column(Float)
    fib_50 = Column(Float)
    fib_382 = Column(Float)
    pivot_point = Column(Float)
    resistance_1 = Column(Float)
    support_1 = Column(Float)

    # Market microstructure
    spread_bps = Column(Float)
    depth_imbalance = Column(Float)
    realized_vol = Column(Float)

    # Regime
    regime_trend = Column(String(20))  # uptrend, downtrend, sideways
    regime_volatility = Column(String(20))  # low, medium, high

    # Sentiment (plugin interface)
    sentiment_score = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)


class Label(Base):
    __tablename__ = "labels"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_labels_symbol_tf_ts"),
        Index("idx_labels_symbol_tf_ts", "symbol", "timeframe", "timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(Enum(TimeFrame), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    side = Column(Enum(Side), nullable=False)

    # Triple barrier
    tp_barrier = Column(Float, nullable=False)
    sl_barrier = Column(Float, nullable=False)
    time_barrier = Column(Integer, nullable=False)  # bars

    # Outcome
    hit_barrier = Column(String(10))  # tp, sl, time
    bars_to_hit = Column(Integer)
    return_pct = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# MODELS & REGISTRY
# ============================================================================

class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String(50), unique=True, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(Enum(TimeFrame), nullable=False)
    model_type = Column(String(50), nullable=False)  # lgbm, xgb, tft, ensemble
    version = Column(String(20), nullable=False)

    # Training metadata
    train_start = Column(DateTime, nullable=False)
    train_end = Column(DateTime, nullable=False)
    oos_start = Column(DateTime, nullable=False)
    oos_end = Column(DateTime, nullable=False)

    # Hyperparameters
    hyperparameters = Column(JSON)

    # Metrics (OOS)
    accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    f1_score = Column(Float)
    roc_auc = Column(Float)
    hit_rate_tp1 = Column(Float)  # Critical metric
    avg_net_profit_pct = Column(Float)  # Critical metric
    sharpe_ratio = Column(Float)
    max_drawdown_pct = Column(Float)

    # Artifacts
    artifact_path = Column(String(255))
    feature_importance = Column(JSON)

    # Status
    is_active = Column(Boolean, default=False)
    is_production = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    deployed_at = Column(DateTime)


class DriftMetrics(Base):
    __tablename__ = "drift_metrics"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String(50), ForeignKey("model_registry.model_id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    psi_score = Column(Float)
    ks_statistic = Column(Float)
    feature_drift_scores = Column(JSON)
    prediction_drift = Column(Float)

    data_freshness_hours = Column(Float)
    drift_detected = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    model = relationship("ModelRegistry")


# ============================================================================
# SIGNALS & TRADES
# ============================================================================

class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(String(50), unique=True, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(Enum(Side), nullable=False)

    # Entry
    entry_price = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Exits
    tp1_price = Column(Float, nullable=False)
    tp1_pct = Column(Float, default=30.0)
    tp2_price = Column(Float, nullable=False)
    tp2_pct = Column(Float, default=40.0)
    tp3_price = Column(Float, nullable=False)
    tp3_pct = Column(Float, default=30.0)
    sl_price = Column(Float, nullable=False)

    # Position sizing
    leverage = Column(Float, nullable=False)
    margin_mode = Column(String(10), default="ISOLATED")
    position_size_usd = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)

    # Risk metrics
    risk_reward_ratio = Column(Float)
    estimated_liquidation = Column(Float)
    max_loss_usd = Column(Float)

    # ML metadata
    model_id = Column(String(50), ForeignKey("model_registry.model_id"))
    confidence = Column(Float)

    # Expected profit
    expected_net_profit_pct = Column(Float, nullable=False)
    expected_net_profit_usd = Column(Float, nullable=False)

    # Validity
    valid_until = Column(DateTime, nullable=False)

    # Status
    status = Column(Enum(SignalStatus), default=SignalStatus.PENDING, index=True)

    # Filters
    passed_spread_check = Column(Boolean, default=True)
    passed_liquidity_check = Column(Boolean, default=True)
    passed_profit_filter = Column(Boolean, default=True)
    passed_correlation_check = Column(Boolean, default=True)
    rejection_reason = Column(Text)

    # Risk profile
    risk_profile = Column(Enum(RiskProfile), nullable=False, index=True)

    # AI-generated summary explaining why this signal is good
    ai_summary = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime)

    model = relationship("ModelRegistry")
    trade_results = relationship("TradeResult", back_populates="signal")


class SignalRejection(Base):
    __tablename__ = "signal_rejections"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(20), nullable=False)
    environment = Column(String(20), nullable=False, default="production")
    model_id = Column(String(50))
    risk_profile = Column(Enum(RiskProfile))
    failed_filters = Column(JSON, nullable=False)
    rejection_reason = Column(Text, nullable=False)
    inference_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class TradeResult(Base):
    __tablename__ = "trade_results"

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(String(50), ForeignKey("signals.signal_id"), nullable=False, index=True)

    # Execution
    entry_filled_price = Column(Float)
    entry_filled_at = Column(DateTime)
    entry_fee_usd = Column(Float)
    entry_slippage_bps = Column(Float)

    # Exits
    tp1_filled_price = Column(Float)
    tp1_filled_at = Column(DateTime)
    tp2_filled_price = Column(Float)
    tp2_filled_at = Column(DateTime)
    tp3_filled_price = Column(Float)
    tp3_filled_at = Column(DateTime)
    sl_filled_price = Column(Float)
    sl_filled_at = Column(DateTime)

    # PnL
    gross_pnl_usd = Column(Float)
    total_fees_usd = Column(Float)
    funding_fees_usd = Column(Float)
    net_pnl_usd = Column(Float)
    net_pnl_pct = Column(Float)

    # Duration
    duration_minutes = Column(Integer)

    # Trailing SL (if activated)
    trailing_activated = Column(Boolean, default=False)
    trailing_sl_price = Column(Float)

    # Final status
    final_status = Column(Enum(SignalStatus))

    created_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime)

    signal = relationship("Signal", back_populates="trade_results")


# ============================================================================
# BACKFILL & JOBS
# ============================================================================

class BackfillJob(Base):
    __tablename__ = "backfill_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(50), unique=True, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(Enum(TimeFrame), nullable=False)

    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    # Progress
    last_completed_ts = Column(DateTime)
    candles_fetched = Column(Integer, default=0)
    total_candles_estimate = Column(Integer)
    progress_pct = Column(Float, default=0.0)

    # Performance
    candles_per_minute = Column(Float)
    eta_minutes = Column(Float)

    # Gaps
    detected_gaps = Column(JSON)  # [{start: ts, end: ts}, ...]

    # Status
    status = Column(String(20), default="pending", index=True)  # pending, running, paused, completed, failed
    error_message = Column(Text)

    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(50), unique=True, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(Enum(TimeFrame), nullable=False)

    # Training parameters
    test_period_days = Column(Integer, default=30)
    min_train_days = Column(Integer, default=180)
    use_expanding_window = Column(Boolean, default=True)

    # Progress
    current_fold = Column(Integer)
    total_folds = Column(Integer)
    progress_pct = Column(Float, default=0.0)
    labeling_progress_pct = Column(Float, default=0.0)

    # Metrics
    accuracy = Column(Float)
    hit_rate_tp1 = Column(Float)
    avg_roc_auc = Column(Float)

    # Model
    model_id = Column(String(50), ForeignKey("model_registry.model_id"), index=True)
    version = Column(String(20))

    # Status
    status = Column(String(20), default="pending", index=True)  # pending, training, completed, failed
    error_message = Column(Text)

    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    elapsed_seconds = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    model = relationship("ModelRegistry")


class SignalGenerationJob(Base):
    __tablename__ = "signal_generation_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(50), unique=True, nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(Enum(TimeFrame), nullable=False)

    # Date range
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)

    # Progress
    signals_generated = Column(Integer, default=0)
    signals_backtested = Column(Integer, default=0)
    total_periods = Column(Integer)
    current_period = Column(Integer)
    progress_pct = Column(Float, default=0.0)

    # Results
    win_rate = Column(Float)
    avg_profit_pct = Column(Float)
    total_pnl_usd = Column(Float)

    # Status
    status = Column(String(20), default="pending", index=True)  # pending, generating, completed, failed
    error_message = Column(Text)

    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    elapsed_seconds = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# USERS & AUTH
# ============================================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)

    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

    # User preferences
    default_risk_profile = Column(Enum(RiskProfile), default=RiskProfile.MEDIUM)
    default_capital_usd = Column(Float, default=100.0)
    preferred_pairs = Column(JSON)  # ["BTC/USDT", "ETH/USDT", ...]

    # API keys (for webhook integration)
    telegram_chat_id = Column(String(100))
    discord_webhook_url = Column(String(255))

    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)


# ============================================================================
# SYSTEM CONFIG
# ============================================================================

class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    description = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CircuitBreaker(Base):
    __tablename__ = "circuit_breakers"

    id = Column(Integer, primary_key=True, index=True)
    breaker_type = Column(String(50), nullable=False, index=True)  # kill_switch, loss_streak, max_dd
    is_triggered = Column(Boolean, default=False, index=True)

    trigger_reason = Column(Text)
    trigger_value = Column(Float)
    threshold = Column(Float)

    triggered_at = Column(DateTime)
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
