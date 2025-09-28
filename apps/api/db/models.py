# apps/api/db/models.py
# PL: Kompletny zestaw modeli zgodny z wymaganiami + indeksy.
# EN: Complete model set per spec + indexes.

import os
from sqlalchemy import (
    Column, String, Integer, Float, JSON, BigInteger, Boolean, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.types import JSON as GenericJSON

USE_GENERIC_JSON = os.getenv("DATABASE_URL", "").startswith("sqlite") or os.getenv("SQLITE_FALLBACK", "1") == "1"

if USE_GENERIC_JSON:
    JSONField = GenericJSON
    def ArrayFloat():  # pragma: no cover - simple helper
        return GenericJSON
else:
    from sqlalchemy.dialects.postgresql import JSONB, ARRAY

    JSONField = JSONB

    def ArrayFloat():
        return ARRAY(Float)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from apps.api.db.base import Base

# --------- Core market/time-series ---------

class OHLCV(Base):
    __tablename__ = "ohlcv"
    # PK i klucz czasowy (epoch ms) – zoptymalizowane pod Timescale hypertable
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    tf: Mapped[str] = mapped_column(String, primary_key=True)  # '1m','15m','1h', etc.
    ts: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # epoch ms
    o: Mapped[float] = mapped_column(Float, nullable=False)
    h: Mapped[float] = mapped_column(Float, nullable=False)
    l: Mapped[float] = mapped_column(Float, nullable=False)
    c: Mapped[float] = mapped_column(Float, nullable=False)
    v: Mapped[float] = mapped_column(Float, nullable=False)
    source_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        Index("ix_ohlcv_ts", "ts"),
        Index("ix_ohlcv_sym_tf_ts_desc", "symbol", "tf", "ts", postgresql_using="btree"),
    )

class Feature(Base):
    __tablename__ = "features"
    symbol: Mapped[str] = mapped_column(String, primary_key=True)
    tf: Mapped[str] = mapped_column(String, primary_key=True)
    ts: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version: Mapped[str] = mapped_column(String, primary_key=True, default="1")
    f_vector: Mapped[dict] = mapped_column(JSONField, nullable=False)

    __table_args__ = (
        Index("ix_features_ts", "ts"),
    )

class BackfillProgress(Base):
    __tablename__ = "backfill_progress"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    tf: Mapped[str] = mapped_column(String, nullable=False)
    last_ts_completed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    chunk_start_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    chunk_end_ts: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="idle")  # idle/running/paused/error/done
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("symbol", "tf", name="uq_backfill_symbol_tf"),
        Index("ix_backfill_status", "status"),
    )

# --------- Signals / Execution / PnL ---------

class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID/KSUID
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    tf_base: Mapped[str] = mapped_column(String, nullable=False)  # np. '15m'
    ts: Mapped[int] = mapped_column(BigInteger, nullable=False)  # event time
    dir: Mapped[str] = mapped_column(String, nullable=False)  # 'LONG'/'SHORT'
    entry: Mapped[float] = mapped_column(Float, nullable=False)
    tp: Mapped[list[float] | None] = mapped_column(ArrayFloat(), nullable=True)  # [tp1,tp2,tp3]
    sl: Mapped[float] = mapped_column(Float, nullable=False)
    lev: Mapped[float] = mapped_column(Float, nullable=False)  # leverage used (planned)
    risk: Mapped[str] = mapped_column(String, nullable=False)  # LOW/MED/HIGH
    margin_mode: Mapped[str] = mapped_column(String, nullable=False, default="ISOLATED")
    expected_net_pct: Mapped[float] = mapped_column(Float, nullable=False)  # musi być >= 0.02
    confidence: Mapped[float] = mapped_column(Float, nullable=True)  # 0..1
    model_ver: Mapped[str] = mapped_column(String, nullable=True)
    reason_discard: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="new")  # new/published/cancelled/expired

    executions: Mapped[list["Execution"]] = relationship("Execution", back_populates="signal", cascade="all, delete-orphan")
    pnl_rows: Mapped[list["PnL"]] = relationship("PnL", back_populates="signal", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_signals_sym_tf_ts", "symbol", "tf_base", "ts"),
        Index("ix_signals_status", "status"),
    )

class Execution(Base):
    __tablename__ = "executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[str] = mapped_column(String, ForeignKey("signals.id", ondelete="CASCADE"))
    side: Mapped[str] = mapped_column(String, nullable=False)  # BUY/SELL
    order_id: Mapped[str | None] = mapped_column(String, nullable=True)
    px: Mapped[float] = mapped_column(Float, nullable=False)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    slippage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # bps or absolute?
    status: Mapped[str] = mapped_column(String, nullable=False, default="filled")
    ts: Mapped[int] = mapped_column(BigInteger, nullable=False)

    signal: Mapped[Signal] = relationship("Signal", back_populates="executions")

    __table_args__ = (
        Index("ix_exec_signal_ts", "signal_id", "ts"),
    )

class PnL(Base):
    __tablename__ = "pnl"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[str] = mapped_column(String, ForeignKey("signals.id", ondelete="CASCADE"))
    realized: Mapped[float | None] = mapped_column(Float, nullable=True)
    unrealized: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_dd: Mapped[float | None] = mapped_column(Float, nullable=True)
    rr: Mapped[float | None] = mapped_column(Float, nullable=True)
    holding_time: Mapped[int | None] = mapped_column(Integer, nullable=True)  # seconds
    funding_paid: Mapped[float | None] = mapped_column(Float, nullable=True)

    signal: Mapped[Signal] = relationship("Signal", back_populates="pnl_rows")

    __table_args__ = (
        Index("ix_pnl_signal", "signal_id"),
    )

# --------- Training / Backtests / Users ---------

class TrainingRun(Base):
    __tablename__ = "training_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[int] = mapped_column(BigInteger, nullable=False)   # epoch ms
    finished_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    params_json: Mapped[dict | None] = mapped_column(JSONField, nullable=True)
    metrics_json: Mapped[dict | None] = mapped_column(JSONField, nullable=True)

    __table_args__ = (
        Index("ix_train_status_start", "status", "started_at"),
    )

class Backtest(Base):
    __tablename__ = "backtests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    params_json: Mapped[dict | None] = mapped_column(JSONField, nullable=True)
    started_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    finished_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    summary_json: Mapped[dict | None] = mapped_column(JSONField, nullable=True)

    trades: Mapped[list["BacktestTrade"]] = relationship("BacktestTrade", back_populates="backtest", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_backtests_start", "started_at"),
    )

class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_id: Mapped[int] = mapped_column(Integer, ForeignKey("backtests.id", ondelete="CASCADE"))
    symbol: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    entry_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    exit_ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    entry: Mapped[float] = mapped_column(Float, nullable=False)
    exit: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    pnl: Mapped[float] = mapped_column(Float, nullable=False)

    backtest: Mapped[Backtest] = relationship("Backtest", back_populates="trades")

    __table_args__ = (
        Index("ix_bt_trades_bt", "backtest_id"),
        Index("ix_bt_trades_sym", "symbol"),
    )

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    risk_profile: Mapped[str] = mapped_column(String, default="LOW")
    capital: Mapped[float] = mapped_column(Float, default=100.0)
    prefs: Mapped[dict | None] = mapped_column(JSONField, nullable=True)
    api_connected: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_users_risk", "risk_profile"),
    )
