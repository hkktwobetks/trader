from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List

from sqlmodel import select

from .db import get_session
from .models import MarketBar


@dataclass
class Trade:
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    pnl: float


@dataclass
class BacktestResult:
    symbol: str
    start: str
    end: str
    initial_equity: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    trades: List[Trade]


def _sma(values: List[float], window: int) -> List[float | None]:
    out: List[float | None] = []
    acc: float = 0.0
    for i, v in enumerate(values):
        acc += v
        if i >= window:
            acc -= values[i - window]
        if i + 1 < window:
            out.append(None)
        else:
            out.append(acc / window)
    return out


def run_sma_crossover(
    symbol: str,
    timeframe: str,
    start: str,
    end: str,
    short_window: int = 5,
    long_window: int = 20,
    initial_equity: float = 100_000.0,
) -> BacktestResult:
    """
    非常にシンプルな SMA クロス戦略:
    - 短期SMAが長期SMAを上抜け → 翌バーの始値でフルエントリー
    - 下抜け → 翌バーの始値でフルクローズ
    - 1銘柄・常にフルポジ or ノーポジ
    """
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)

    with get_session() as s:
        bars = s.exec(
            select(MarketBar)
            .where(
                MarketBar.symbol == symbol,
                MarketBar.timeframe == timeframe,
                MarketBar.ts >= start_dt,
                MarketBar.ts <= end_dt,
            )
            .order_by(MarketBar.ts)
        ).all()

    if not bars:
        return BacktestResult(
            symbol=symbol,
            start=start,
            end=end,
            initial_equity=initial_equity,
            final_equity=initial_equity,
            total_return_pct=0.0,
            max_drawdown_pct=0.0,
            trades=[],
        )

    closes = [b.close for b in bars]
    short_sma = _sma(closes, short_window)
    long_sma = _sma(closes, long_window)

    in_position = False
    entry_price = 0.0
    equity = initial_equity
    peak = initial_equity
    max_dd_pct = 0.0
    trades: List[Trade] = []

    for i in range(1, len(bars)):
        prev_short = short_sma[i - 1]
        prev_long = long_sma[i - 1]
        cur_short = short_sma[i]
        cur_long = long_sma[i]

        # シグナルがまだ計算できない期間はスキップ
        if prev_short is None or prev_long is None or cur_short is None or cur_long is None:
            continue

        bar_next = bars[i]
        price = bar_next.open

        # クロス判定（シンプルに sign の変化を見る）
        prev_diff = prev_short - prev_long
        cur_diff = cur_short - cur_long

        # ゴールデンクロス: ノーポジ → ロング
        if not in_position and prev_diff <= 0 < cur_diff:
            in_position = True
            entry_price = price
            continue

        # デッドクロス: ロング → ノーポジ
        if in_position and prev_diff >= 0 > cur_diff:
            in_position = False
            exit_price = price
            pnl_price = exit_price - entry_price
            # 1単位あたりのPnLを equity にスケール
            size = equity / entry_price
            trade_pnl = pnl_price * size
            equity += trade_pnl
            trades.append(
                Trade(
                    entry_date=bars[i - 1].ts.date().isoformat(),
                    exit_date=bar_next.ts.date().isoformat(),
                    entry_price=entry_price,
                    exit_price=exit_price,
                    pnl=trade_pnl,
                )
            )

        peak = max(peak, equity)
        if peak > 0:
            dd = (equity - peak) / peak * 100.0
            max_dd_pct = min(max_dd_pct, dd)

    total_return_pct = (equity / initial_equity - 1.0) * 100.0

    return BacktestResult(
        symbol=symbol,
        start=start,
        end=end,
        initial_equity=initial_equity,
        final_equity=equity,
        total_return_pct=total_return_pct,
        max_drawdown_pct=max_dd_pct,
        trades=trades,
    )

