from pydantic import BaseModel


class ExtractedSignal(BaseModel):
    ticker: str
    side: str
    confidence: float | None = None
    timeframe: str | None = None
    stop: float | None = None
    take: float | None = None


class OrderIn(BaseModel):
    ticker: str
    side: str
    qty: float
    price: float | None = None