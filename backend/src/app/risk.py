from .config import settings
from .models import Position
from sqlmodel import select
from .db import get_session


class RiskGuard:
    def __init__(self):
        self.max_daily_loss = settings.max_daily_loss
        self.max_pos_per_ticker = settings.max_position_per_ticker

    def can_open(self, ticker: str, qty_delta: float) -> bool:
        # 簡易: ティッカー別の建玉上限のみチェック
        with get_session() as s:
            pos = s.exec(select(Position).where(Position.ticker == ticker)).first()
            current = 0.0 if not pos else pos.qty
            return abs(current + qty_delta) <= self.max_pos_per_ticker


risk_guard = RiskGuard()