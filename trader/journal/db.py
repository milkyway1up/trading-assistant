"""SQLAlchemy models for the trade journal. Phase 4."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import (Column, DateTime, Float, ForeignKey, Integer, String,
                        Text, create_engine)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    schwab_order_id = Column(String, unique=True, index=True, nullable=True)
    ticker = Column(String, nullable=False, index=True)
    side = Column(String, nullable=False)  # buy / sell
    setup_type = Column(String, nullable=True, index=True)

    entry_time = Column(DateTime, nullable=True)
    entry_price = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    exit_price = Column(Float, nullable=True)

    quantity = Column(Integer, nullable=False)
    stop_price = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    risk_dollars = Column(Float, nullable=True)
    realized_pnl = Column(Float, nullable=True)
    r_multiple = Column(Float, nullable=True)

    thesis_at_entry = Column(Text, nullable=True)
    catalysts = Column(Text, nullable=True)
    mistakes = Column(Text, nullable=True)
    exit_reason = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    screenshot_path = Column(String, nullable=True)

    llm_grade = Column(String, nullable=True)  # A/B/C/D/F
    llm_lesson = Column(Text, nullable=True)
    llm_tags = Column(Text, nullable=True)  # comma-separated

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def get_engine(db_path: str | Path = "data/journal.db"):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    Base.metadata.create_all(engine)
    return engine


def get_session(db_path: str | Path = "data/journal.db"):
    return sessionmaker(bind=get_engine(db_path), future=True, expire_on_commit=False)()
