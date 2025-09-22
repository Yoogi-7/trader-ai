
from sqlalchemy import (
    Column, String, Integer, Float, JSON, TIMESTAMP, BigInteger, Boolean, ForeignKey, ARRAY
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from apps.api.db.base import Base

class OHLCV(Base):
    __tablename__ = "ohlcv"
    symbol = Column(String, primary_key=True)
    tf = Column(String, primary_key=True)
    ts = Column(BigInteger, primary_key=True)  # epoch ms
    o = Column(Float, nullable=False)
    h = Column(Float, nullable=False)
    l = Column(Float, nullable=False)
    c = Column(Float, nullable=False)
    v = Column(Float, nullable=False)
    source_hash = Column(String, nullable=True)

class Feature(Base):
    __tablename__ = "features"
    symbol = Column(String, primary_key=True)
    tf = Column(String, primary_key=True)
    ts = Column(BigInteger, primary_key=True)
    version = Column(String, primary_key=True)
    f_vector = Column(JSONB, nullable=False)

class BackfillProgress(Base):
    __tablename__ = "backfill_progress"
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String, nullable=False)
    tf = Column(String, nullable=False)
    last_ts_completed = Column(BigInteger, nullable=True)
    chunk_start_ts = Column(BigInteger, nullable=True)
    chunk_end_ts = Column(BigInteger, nullable=True)
    retry_count = Column(Integer, default=0)
    status = Column(String, default="idle")  # idle/running/failed/done
    updated_at = Column(TIMESTAMP, nullable=True)
    gaps = Column(JSONB, nullable=True)

class Signal(Base):
    __tablename__ = "signals"
    id = Column(String, primary_key=True)  # uuid
    symbol = Column(String, nullable=False)
    tf_base = Column(String, nullable=False)
    ts = Column(BigInteger, nullable=False)
    dir = Column(String, nullable=False)  # long/short
    entry = Column(Float, nullable=False)
    tp = Column(ARRAY(Float), nullable=False)  # [tp1,tp2,tp3]
    sl = Column(Float, nullable=False)
    lev = Column(Integer, nullable=False)
    risk = Column(Float, nullable=False)
    margin_mode = Column(String, default="isolated")
    expected_net_pct = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    model_ver = Column(String, nullable=False)
    reason_discard = Column(String, nullable=True)
    status = Column(String, default="new")  # new/published/filled/cancelled

class Execution(Base):
    __tablename__ = "executions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(String, ForeignKey("signals.id"))
    order_id = Column(String, nullable=True)
    side = Column(String, nullable=False)
    px = Column(Float, nullable=False)
    qty = Column(Float, nullable=False)
    fee = Column(Float, nullable=False)
    slippage = Column(Float, nullable=True)
    status = Column(String, default="new")
    ts = Column(BigInteger, nullable=False)

class PnL(Base):
    __tablename__ = "pnl"
    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(String, ForeignKey("signals.id"))
    realized = Column(Float, nullable=True)
    unrealized = Column(Float, nullable=True)
    max_dd = Column(Float, nullable=True)
    rr = Column(Float, nullable=True)
    holding_time = Column(Integer, nullable=True)  # minutes
    funding_paid = Column(Float, nullable=True)

class TrainingRun(Base):
    __tablename__ = "training_runs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(TIMESTAMP, nullable=True)
    finished_at = Column(TIMESTAMP, nullable=True)
    status = Column(String, default="pending")
    params_json = Column(JSONB, nullable=True)
    metrics_json = Column(JSONB, nullable=True)

class Backtest(Base):
    __tablename__ = "backtests"
    id = Column(Integer, primary_key=True, autoincrement=True)
    params_json = Column(JSONB, nullable=True)
    started_at = Column(TIMESTAMP, nullable=True)
    finished_at = Column(TIMESTAMP, nullable=True)
    summary_json = Column(JSONB, nullable=True)

class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    id = Column(Integer, primary_key=True, autoincrement=True)
    backtest_id = Column(Integer, ForeignKey("backtests.id"))
    symbol = Column(String, nullable=False)
    entry_ts = Column(BigInteger, nullable=False)
    exit_ts = Column(BigInteger, nullable=False)
    entry = Column(Float, nullable=False)
    exit = Column(Float, nullable=False)
    fee = Column(Float, nullable=False)
    pnl = Column(Float, nullable=False)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    risk_profile = Column(String, default="LOW")
    capital = Column(Float, default=100.0)
    prefs = Column(JSONB, nullable=True)
    api_connected = Column(Boolean, default=False)
