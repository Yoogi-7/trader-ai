from sqlalchemy import Column, Integer, String, Float, Boolean, JSON, BigInteger, UniqueConstraint, ARRAY
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from apps.api.db import Base

class OHLCV(Base):
    __tablename__ = "ohlcv"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True, nullable=False)
    tf = Column(String, index=True, nullable=False)
    ts = Column(BigInteger, index=True, nullable=False)  # epoch ms
    o = Column(Float); h = Column(Float); l = Column(Float); c = Column(Float); v = Column(Float)
    source_hash = Column(String, nullable=True)
    __table_args__ = (UniqueConstraint("symbol","tf","ts", name="u_ohlcv_idx"),)

class Feature(Base):
    __tablename__ = "features"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True, nullable=False)
    tf = Column(String, index=True, nullable=False)
    ts = Column(BigInteger, index=True, nullable=False)
    f_vector = Column(JSON, nullable=False)
    version = Column(String, default="v1")
    __table_args__ = (UniqueConstraint("symbol","tf","ts","version", name="u_features_idx"),)

class BackfillProgress(Base):
    __tablename__ = "backfill_progress"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    tf = Column(String, index=True)
    last_ts_completed = Column(BigInteger, default=0)
    chunk_start_ts = Column(BigInteger, default=0)
    chunk_end_ts = Column(BigInteger, default=0)
    retry_count = Column(Integer, default=0)
    status = Column(String, default="idle")
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("symbol","tf", name="u_backfill_idx"),)

class Signal(Base):
    __tablename__ = "signals"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    tf_base = Column(String, default="15m")
    ts = Column(BigInteger, index=True)
    dir = Column(String)  # long/short
    entry = Column(Float); sl = Column(Float)
    tp = Column(ARRAY(Float))
    lev = Column(Integer); risk = Column(Float)
    margin_mode = Column(String, default="isolated")
    expected_net_pct = Column(Float)
    confidence = Column(Float)
    model_ver = Column(String)
    reason_discard = Column(String, nullable=True)
    status = Column(String, default="published")  # or discarded

class Execution(Base):
    __tablename__ = "executions"
    id = Column(Integer, primary_key=True)
    signal_id = Column(Integer, index=True)
    order_id = Column(String)
    side = Column(String)
    px = Column(Float); qty = Column(Float)
    fee = Column(Float); slippage = Column(Float)
    status = Column(String); ts = Column(BigInteger, index=True)

class PnL(Base):
    __tablename__ = "pnl"
    id = Column(Integer, primary_key=True)
    signal_id = Column(Integer, index=True)
    realized = Column(Float); unrealized = Column(Float)
    max_dd = Column(Float); rr = Column(Float)
    holding_time = Column(Integer)
    funding_paid = Column(Float, default=0.0)

class TrainingRun(Base):
    __tablename__ = "training_runs"
    id = Column(Integer, primary_key=True)
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)
    status = Column(String, default="running")
    params_json = Column(JSON); metrics_json = Column(JSON)

class Backtest(Base):
    __tablename__ = "backtests"
    id = Column(Integer, primary_key=True)
    params_json = Column(JSON); started_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    finished_at = Column(TIMESTAMP(timezone=True), nullable=True)
    summary_json = Column(JSON)

class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    id = Column(Integer, primary_key=True)
    signal_id = Column(Integer, index=True); entry = Column(Float); exit = Column(Float)
    fee = Column(Float); pnl = Column(Float); hit_tp_level = Column(Integer, default=0)
    opened_at = Column(BigInteger); closed_at = Column(BigInteger)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    risk_profile = Column(String, default="LOW")
    capital = Column(Float, default=100.0)
    prefs = Column(JSON, default={})
    api_connected = Column(Boolean, default=False)

# === NEW: Funding rates ===
class FundingRate(Base):
    __tablename__ = "funding_rates"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True, nullable=False)
    ts = Column(BigInteger, index=True, nullable=False)
    rate_bps = Column(Float, nullable=False)  # funding rate * 10000
    __table_args__ = (UniqueConstraint("symbol","ts", name="u_funding_idx"),)

# === NEW: Open Interest ===
class OpenInterest(Base):
    __tablename__ = "open_interest"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True, nullable=False)
    ts = Column(BigInteger, index=True, nullable=False)
    oi = Column(Float, nullable=False)  # nominal OI (np. w USDT)
    __table_args__ = (UniqueConstraint("symbol","ts", name="u_oi_idx"),)
