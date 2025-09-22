from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from sqlalchemy import Integer, String, Numeric, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    risk_profile: Mapped[str] = mapped_column(String(10))
    capital: Mapped[float] = mapped_column(Numeric(18,4))
    prefs: Mapped[dict | None] = mapped_column(JSONB)
    api_connected: Mapped[bool] = mapped_column(Boolean, default=False)

class Signal(Base):
    __tablename__ = "signals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(Text)
    tf_base: Mapped[str] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    dir: Mapped[str] = mapped_column(String(4))
    entry: Mapped[float] = mapped_column(Numeric(18,8))
    tp1: Mapped[float | None] = mapped_column(Numeric(18,8))
    tp2: Mapped[float | None] = mapped_column(Numeric(18,8))
    tp3: Mapped[float | None] = mapped_column(Numeric(18,8))
    sl: Mapped[float] = mapped_column(Numeric(18,8))
    lev: Mapped[float] = mapped_column(Numeric(10,2))
    risk: Mapped[float] = mapped_column(Numeric(6,3))
    margin_mode: Mapped[str] = mapped_column(String(10))
    expected_net_pct: Mapped[float] = mapped_column(Numeric(6,3))
    confidence: Mapped[float | None] = mapped_column(Numeric(6,3))
    model_ver: Mapped[str | None] = mapped_column(String(50))
    reason_discard: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(20), default="published")
