from sqlalchemy import Column, Integer, String, Float, Boolean, JSON, BigInteger, UniqueConstraint, ARRAY
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.sql import func
from apps.api.db import Base

# ===== Hypertable: OHLCV =====
class OHLCV(Base):
    __tablename__ = "ohlcv"
    # PK zgodny z Timescale: zawiera kolumnę partycjonującą 'tstz'
    symbol = Column(String, primary_key=True, index=True, nullable=False)
    tf     = Column(String, primary_key=True, index=True, nullable=False)
    tstz   = Column(TIMESTAMP(timezone=True), primary_key=True, nullable=False)

    # pozostałe pola
    ts = Column(BigInteger, index=True, nullable=False)  # epoch ms (pomocniczo)
    o = Column(Float); h = Column(Float); l = Column(Float); c = Column(Float); v = Column(Float)
    source_hash = Column(String, nullable=True)

# ===== Hypertable: FEATURES =====
class Feature(Base):
    __tablename__ = "features"
    symbol  = Column(String, primary_key=True, index=True, nullable=False)
    tf      = Column(String, primary_key=True, index=True, nullable=False)
    tstz    = Column(TIMESTAMP(timezone=True), primary_key=True, nullable=False)
    version = Column(String, primary_key=True, default="v1")

    ts = Column(BigInteger, index=True, nullable=False)
    f_vector = Column(JSON, nullable=False)

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

class Signal(Base):
    __tablename__ = "signals"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)
    tf_base = Column(String, default="15m")
    ts = Column(BigInteger, index=True)
    dir = Column(String)
    entry = Column(Float); sl = Column(Float)
    tp = Column(ARRAY(Float))
    lev = Column(Integer); risk = Column(Float)
    margin_mode = Column(String, default="isolated")
    expected_net_pct = Column(Float)
    confidence = Column(Float)
    model_ver = Column(String)
    reason_discard = Column(String, nullable=True)
    status = Column(String, default="published")

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

class FundingRate(Base):
    __tablename__ = "funding_rates"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True, nullable=False)
    ts = Column(BigInteger, index=True, nullable=False)
    rate_bps = Column(Float, nullable=False)

class OpenInterest(Base):
    __tablename__ = "open_interest"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True, nullable=False)
    ts = Column(BigInteger, index=True, nullable=False)
    oi = Column(Float, nullable=False)

class OrderBookSnapshot(Base):
    __tablename__ = "orderbook_snapshots"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True, nullable=False)
    ts = Column(BigInteger, index=True, nullable=False)
    bid_px = Column(Float, nullable=False); bid_qty = Column(Float, nullable=False)
    ask_px = Column(Float, nullable=False); ask_qty = Column(Float, nullable=False)
    mid_px = Column(Float, nullable=False); spread_bps = Column(Float, nullable=False)
    depth_usd_1pct = Column(Float, nullable=False)

class Position(Base):
    __tablename__ = "positions"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True, nullable=False)
    side = Column(String, nullable=False)
    entry_px = Column(Float, nullable=False)
    qty = Column(Float, nullable=False)
    lev = Column(Integer, nullable=False)
    margin_mode = Column(String, default="isolated")
    exposure_usd = Column(Float, nullable=False)
    opened_ts = Column(BigInteger, index=True, nullable=False)
    status = Column(String, default="open")
    pnl = Column(Float, default=0.0)
