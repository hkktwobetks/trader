from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import prod
from typing import Iterable, List

from .models import PnL


@dataclass
class EquityPoint:
    date: str
    equity: float


@dataclass
class PerformanceSummary:
    start_date: str | None
    end_date: str | None
    initial_equity: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float | None
    max_drawdown_pct: float
    equity_curve: List[EquityPoint]


def _parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def build_equity_from_pnl(pnls: Iterable[PnL], initial_equity: float = 100_000.0) -> PerformanceSummary:
    """
    非常にシンプルなモデル:
    - 日次 realized をそのまま損益として initial_equity に累積する
    - unrealized は無視（将来の拡張用）
    """
    pnls_list = sorted(pnls, key=lambda x: x.date)
    if not pnls_list:
        return PerformanceSummary(
            start_date=None,
            end_date=None,
            initial_equity=initial_equity,
            final_equity=initial_equity,
            total_return_pct=0.0,
            cagr_pct=None,
            max_drawdown_pct=0.0,
            equity_curve=[],
        )

    equity = initial_equity
    equity_curve: List[EquityPoint] = []
    peak = initial_equity
    max_dd_pct = 0.0

    for row in pnls_list:
        equity += row.realized
        equity_curve.append(EquityPoint(date=row.date, equity=equity))
        if equity > peak:
            peak = equity
        drawdown = (equity - peak) / peak if peak > 0 else 0.0
        max_dd_pct = min(max_dd_pct, drawdown * 100.0)

    start_date = pnls_list[0].date
    end_date = pnls_list[-1].date
    total_return_pct = (equity / initial_equity - 1.0) * 100.0

    # 日数から CAGR をざっくり計算
    try:
        days = (_parse_date(end_date) - _parse_date(start_date)).days or 1
        years = days / 365.25
        cagr = (equity / initial_equity) ** (1 / years) - 1 if years > 0 else 0.0
        cagr_pct: float | None = cagr * 100.0
    except Exception:
        cagr_pct = None

    return PerformanceSummary(
        start_date=start_date,
        end_date=end_date,
        initial_equity=initial_equity,
        final_equity=equity,
        total_return_pct=total_return_pct,
        cagr_pct=cagr_pct,
        max_drawdown_pct=max_dd_pct,
        equity_curve=equity_curve,
    )

