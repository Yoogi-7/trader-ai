
from __future__ import annotations
from sqlalchemy import (
    Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint, Index, JSON as SAJSON
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import datetime

class Base(DeclarativeBase):
    pass

class OHLCV(Base):
    __tablename__ = "ohlcv"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    tf: Mapped[str] = mapped_column(String(8), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)  # UTC
    o: Mapped[float] = mapped_column(Float)
    h: Mapped[float] = mapped_column(Float)
    l: Mapped[float] = mapped_column(Float)
    c: Mapped[float] = mapped_column(Float)
    v: Mapped[float] = mapped_column(Float)
    source_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    __table_args__ = (
        UniqueConstraint("symbol", "tf", "ts", name="uq_ohlcv_symbol_tf_ts"),
        Index("idx_ohlcv_symbol_tf_ts", "symbol", "tf", "ts"),
    )

class BackfillProgress(Base):
    __tablename__ = "backfill_progress"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    tf: Mapped[str] = mapped_column(String(8), index=True)
    last_ts_completed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    chunk_start_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    chunk_end_ts: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="idle")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("symbol", "tf", name="uq_backfill_symbol_tf"),)

class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    tf_base: Mapped[str] = mapped_column(String(8), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    direction: Mapped[str] = mapped_column(String(5))  # LONG/SHORT
    entry: Mapped[float] = mapped_column(Float)
    tp1: Mapped[float] = mapped_column(Float)
    tp2: Mapped[float] = mapped_column(Float)
    tp3: Mapped[float] = mapped_column(Float)
    sl: Mapped[float] = mapped_column(Float)
    leverage: Mapped[int] = mapped_column(Integer)
    risk_pct: Mapped[float] = mapped_column(Float)
    margin_mode: Mapped[str] = mapped_column(String(10))  # isolated/cross
    expected_net_pct: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    model_ver: Mapped[str] = mapped_column(String(50))
    reason_discard: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="published")  # published/rejected

class Execution(Base):
    __tablename__ = "executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int] = mapped_column(Integer, ForeignKey("signals.id", ondelete="CASCADE"))
    order_id: Mapped[str] = mapped_column(String(40))
    side: Mapped[str] = mapped_column(String(5))
    px: Mapped[float] = mapped_column(Float)
    qty: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float, default=0.0)
    slippage_bps: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(16))  # filled/cancelled/etc.
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)

class PnL(Base):
    __tablename__ = "pnl"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int] = mapped_column(Integer, ForeignKey("signals.id", ondelete="CASCADE"))
    realized: Mapped[float] = mapped_column(Float)
    unrealized: Mapped[float] = mapped_column(Float)
    max_dd: Mapped[float] = mapped_column(Float)
    rr: Mapped[float] = mapped_column(Float)  # risk-reward
    holding_time_min: Mapped[int] = mapped_column(Integer)
    funding_paid: Mapped[float] = mapped_column(Float, default=0.0)

class TrainingRun(Base):
    __tablename__ = "training_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    params_json: Mapped[dict] = mapped_column(SAJSON, default=dict)
    metrics_json: Mapped[dict] = mapped_column(SAJSON, default=dict)

class Backtest(Base):
    __tablename__ = "backtests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    params_json: Mapped[dict] = mapped_column(SAJSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    risk_profile: Mapped[str] = mapped_column(String(8), default="LOW")
    capital: Mapped[float] = mapped_column(Float, default=100.0)
    prefs: Mapped[dict | None] = mapped_column(SAJSON, nullable=True)
    api_connected: Mapped[bool] = mapped_column(Boolean, default=False)
