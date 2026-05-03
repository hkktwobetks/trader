from typing import Any, Dict
from pydantic import BaseModel, Field


class ExtractedSignal(BaseModel):
    ticker: str
    side: str
    confidence: float | None = None
    timeframe: str | None = None
    entry: float | None = None
    stop: float | None = None
    take: float | None = None
    targets: list[float] = []


class OrderIn(BaseModel):
    ticker: str
    side: str
    qty: float
    price: float | None = None


class SignalIn(BaseModel):
    text: str
    source: str
    meta: Dict[str, Any] = Field(default_factory=dict)
