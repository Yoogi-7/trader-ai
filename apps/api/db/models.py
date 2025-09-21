# apps/api/db/models.py
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, Boolean
from sqlalchemy.dialects.postgresql import JSON

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    risk_profile = Column(String, nullable=False, default="LOW")
    capital = Column(Float, nullable=False, default=100.0)
    prefs = Column(JSON)
    api_connected = Column(Boolean, default=False)
