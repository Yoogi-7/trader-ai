from __future__ import annotations
from sqlalchemy import (
    Column, Integer, BigInteger, String, Float, Boolean, DateTime, JSON,
    ForeignKey, UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from datetime import datetime

class Base(DeclarativeBase):
    pass

class OHLCV(Base):
    __tablename__ = "ohlcv"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), index=True)
    tf: Mapped[str] = mapped_column(String(8), index=True)  # "1m","15m","1h"
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
    direction: Mapped[str] = mapped_column(String(4))  # "LONG"/"SHORT"
    entry: Mapped[float] = mapped_column(Float)
    tp1: Mapped[float] = mapped_column(Float)
    tp2: Mapped[float] = mapped_column(Float)
    tp3: Mapped[float] = mapped_column(Float)
    sl: Mapped[float] = mapped_column(Float)
    leverage: Mapped[int] = mapped_column(Integer)
    risk_pct: Mapped[float] = mapped_column(Float)  # ryzyko względem kapitału
    margin_mode: Mapped[str] = mapped_column(String(10))  # "isolated"/"cross"
    expected_net_pct: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)  # 0..1
    model_ver: Mapped[str] = mapped_column(String(50))
    reason_discard: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="published")  # "draft"/"published"/"rejected"

class Execution(Base):
    __tablename__ = "executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[int] = mapped_column(Integer, ForeignKey("signals.id", ondelete="CASCADE"))
    side: Mapped[str] = mapped_column(String(4))  # buy/sell
    px: Mapped[float] = mapped_column(Float)
    qty: Mapped[float] = mapped_column(Float)
    fee: Mapped[float] = mapped_column(Float)
    slippage: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16))
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    signal: Mapped[Signal] = relationship()

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
