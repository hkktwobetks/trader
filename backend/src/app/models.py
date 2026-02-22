from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime


class Signal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    message_id: str
    author: str
    channel_id: int
    content: str
    ticker: str
    side: str # BUY/SELL
    confidence: float | None = None
    timeframe: str | None = None
    stop: float | None = None
    take: float | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    broker: str
    ticker: str
    side: str # BUY/SELL
    qty: float
    price: float | None = None
    status: str = "NEW" # NEW/FILLED/CANCELED/REJECTED
    reason: str | None = None
    signal_id: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Position(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str
    qty: float # + long / - short（紙取引用の簡易モデル）
    avg_price: float


class Execution(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int
    ticker: str
    side: str
    qty: float
    price: float
    executed_at: datetime = Field(default_factory=datetime.utcnow)


class PnL(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: str # YYYY-MM-DD
    realized: float = 0.0
    unrealized: float = 0.0