import os
from datetime import datetime
from typing import Iterable

from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from sqlmodel import select

from app.config import settings
from app.db import get_session
from app.models import MarketBar


def _parse_timeframe(tf: str) -> TimeFrame:
    tf = tf.lower()
    if tf in {"1min", "1m"}:
        return TimeFrame.Minute
    if tf in {"5min", "5m"}:
        return TimeFrame(5, "Min")
    if tf in {"15min", "15m"}:
        return TimeFrame(15, "Min")
    if tf in {"1h", "1hour"}:
        return TimeFrame.Hour
    if tf in {"1d", "day", "1day"}:
        return TimeFrame.Day
    raise ValueError(f"Unsupported timeframe: {tf}")


def fetch_and_store_bars(
    symbols: Iterable[str],
    timeframe: str = "1Day",
    start: str | None = None,
    end: str | None = None,
) -> None:
    """
    Alpaca からヒストリカルバーを取得し、MarketBar テーブルに保存する。

    :param symbols: 取得対象ティッカー（例: ["AAPL", "MSFT"]）
    :param timeframe: "1Min", "5Min", "1Day" など
    :param start: 開始日 (YYYY-MM-DD) 省略時は API デフォルト
    :param end: 終了日 (YYYY-MM-DD) 省略時は API デフォルト
    """
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        raise RuntimeError("Alpaca API キーが設定されていません")

    tf = _parse_timeframe(timeframe)
    client = StockHistoricalDataClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
    )

    req = StockBarsRequest(
        symbol_or_symbols=list(symbols),
        timeframe=tf,
        start=datetime.fromisoformat(start) if start else None,
        end=datetime.fromisoformat(end) if end else None,
    )

    bars_resp = client.get_stock_bars(req)

    with get_session() as session:
        for symbol, bars in bars_resp.data.items():
            for bar in bars:
                # 既に同一キー（symbol, timeframe, ts）があればスキップ
                exists = session.exec(
                    select(MarketBar).where(
                        MarketBar.symbol == symbol,
                        MarketBar.timeframe == timeframe,
                        MarketBar.ts == bar.timestamp,
                    )
                ).first()
                if exists:
                    continue

                mb = MarketBar(
                    symbol=symbol,
                    timeframe=timeframe,
                    ts=bar.timestamp,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=float(bar.volume),
                )
                session.add(mb)

        session.commit()


def main() -> None:
    symbols_env = os.getenv("ALPACA_SYMBOLS", "AAPL,MSFT")
    symbols = [s.strip().upper() for s in symbols_env.split(",") if s.strip()]
    timeframe = os.getenv("ALPACA_TIMEFRAME", "1Day")
    start = os.getenv("ALPACA_START")  # YYYY-MM-DD
    end = os.getenv("ALPACA_END")  # YYYY-MM-DD

    fetch_and_store_bars(symbols, timeframe=timeframe, start=start, end=end)


if __name__ == "__main__":
    main()

