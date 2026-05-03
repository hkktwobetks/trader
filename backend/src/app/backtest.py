from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, List, Optional

from sqlmodel import select

from .db import get_session
from .models import MarketBar, Signal


# ── SMA crossover (legacy) ────────────────────────────────────────────────────

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


def _sma(values: List[float], window: int) -> List[Optional[float]]:
    out: List[Optional[float]] = []
    acc: float = 0.0
    for i, v in enumerate(values):
        acc += v
        if i >= window:
            acc -= values[i - window]
        out.append(None if i + 1 < window else acc / window)
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
            symbol=symbol, start=start, end=end,
            initial_equity=initial_equity, final_equity=initial_equity,
            total_return_pct=0.0, max_drawdown_pct=0.0, trades=[],
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
        ps, pl = short_sma[i - 1], long_sma[i - 1]
        cs, cl = short_sma[i], long_sma[i]
        if any(v is None for v in (ps, pl, cs, cl)):
            continue

        price = bars[i].open
        prev_diff = ps - pl  # type: ignore
        cur_diff = cs - cl   # type: ignore

        if not in_position and prev_diff <= 0 < cur_diff:
            in_position = True
            entry_price = price
            continue

        if in_position and prev_diff >= 0 > cur_diff:
            in_position = False
            size = equity / entry_price
            trade_pnl = (price - entry_price) * size
            equity += trade_pnl
            trades.append(Trade(
                entry_date=bars[i - 1].ts.date().isoformat(),
                exit_date=bars[i].ts.date().isoformat(),
                entry_price=entry_price,
                exit_price=price,
                pnl=trade_pnl,
            ))

        peak = max(peak, equity)
        if peak > 0:
            dd = (equity - peak) / peak * 100.0
            max_dd_pct = min(max_dd_pct, dd)

    return BacktestResult(
        symbol=symbol, start=start, end=end,
        initial_equity=initial_equity, final_equity=equity,
        total_return_pct=(equity / initial_equity - 1.0) * 100.0,
        max_drawdown_pct=max_dd_pct,
        trades=trades,
    )


# ── Signal replay backtest ────────────────────────────────────────────────────

@dataclass
class SignalTrade:
    signal_id: int
    ticker: str
    side: str
    signal_date: str
    entry_price: float
    stop: Optional[float]
    first_target: Optional[float]
    exit_price: Optional[float]
    exit_date: Optional[str]
    outcome: str          # "win" | "loss" | "open" | "no_data" | "no_target" | "no_entry"
    pnl: float
    qty: float
    rr_ratio: Optional[float]


@dataclass
class SignalBacktestResult:
    start: str
    end: str
    ticker_filter: Optional[str]
    total_signals: int
    tradeable: int
    wins: int
    losses: int
    open_trades: int
    win_rate_pct: float
    total_pnl: float
    avg_rr: Optional[float]
    trades: List[SignalTrade]


def _f(v: Any) -> Optional[float]:
    """Safely coerce a value to float (handles SQLite text-stored numbers)."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_first_target(sig: Signal) -> Optional[float]:
    if sig.targets:
        try:
            ts = json.loads(sig.targets)
            if ts:
                return float(ts[0])
        except Exception:
            pass
    return _f(sig.take)


def _simulate(
    side: str,
    entry: float,
    stop: Optional[float],
    target: Optional[float],
    df: Any,
    sig_date: date,
) -> tuple[str, Optional[float], Optional[str]]:
    """Scan forward bars and return (outcome, exit_price, exit_date)."""
    if df is None or df.empty:
        return "no_data", None, None
    if stop is None and target is None:
        return "no_target", None, None

    # Filter to bars on or after the signal date
    try:
        idx_dates = df.index.date
    except AttributeError:
        idx_dates = df.index.to_pydatetime()
        idx_dates = [d.date() for d in idx_dates]
    mask = [d >= sig_date for d in idx_dates]
    rows = df.loc[mask]

    if rows.empty:
        return "no_data", None, None

    is_long = side.upper() == "BUY"

    for idx, row in rows.iterrows():
        try:
            o = float(row["Open"])
            h = float(row["High"])
            lo = float(row["Low"])
        except Exception:
            continue
        # Derive a human-readable datetime string
        try:
            d = idx.isoformat()[:16]  # "YYYY-MM-DDTHH:MM" for intraday, "YYYY-MM-DD" for daily
        except Exception:
            d = str(idx)[:16]

        if is_long:
            if stop is not None and o <= stop:
                return "loss", stop, d
            if stop is not None and lo <= stop:
                return "loss", stop, d
            if target is not None and h >= target:
                return "win", target, d
        else:
            if stop is not None and o >= stop:
                return "loss", stop, d
            if stop is not None and h >= stop:
                return "loss", stop, d
            if target is not None and lo <= target:
                return "win", target, d

    return "open", None, None


# intraday intervals and their max lookback in days (yfinance limit)
_INTERVAL_MAX_DAYS: dict[str, int] = {
    "1m": 7,
    "2m": 60,
    "5m": 60,
    "15m": 60,
    "30m": 60,
    "60m": 730,
    "1h": 730,
    "1d": 9999,
}


def _download_bars(sym: str, dl_start: str, dl_end: str, interval: str) -> Any:
    """Download OHLCV from yfinance; returns None on failure or empty data."""
    import yfinance as yf
    try:
        df = yf.download(
            sym, start=dl_start, end=dl_end,
            interval=interval, auto_adjust=True, progress=False,
        )
        if df.empty:
            return None
        # Flatten MultiIndex columns (e.g. when yfinance returns per-ticker level)
        if hasattr(df.columns, "levels"):
            df.columns = df.columns.get_level_values(0)
        # Strip timezone so .date comparisons work uniformly
        if hasattr(df.index, "tz") and df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df
    except Exception:
        return None


def run_signal_backtest(
    ticker: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    qty: float = 100.0,
    interval: str = "5m",
) -> SignalBacktestResult:
    from datetime import date as date_type

    with get_session() as sess:
        q = select(Signal)
        if ticker:
            q = q.where(Signal.ticker == ticker.upper())
        if start:
            q = q.where(Signal.created_at >= datetime.fromisoformat(start))
        if end:
            q = q.where(Signal.created_at <= datetime.fromisoformat(end + "T23:59:59"))
        signals = sess.exec(q.order_by(Signal.created_at)).all()

    empty = SignalBacktestResult(
        start=start or "", end=end or "", ticker_filter=ticker,
        total_signals=0, tradeable=0, wins=0, losses=0, open_trades=0,
        win_rate_pct=0.0, total_pnl=0.0, avg_rr=None, trades=[],
    )
    if not signals:
        return empty

    max_days = _INTERVAL_MAX_DAYS.get(interval, 60)
    today = date_type.today()

    all_dates = [s.created_at.date() for s in signals]
    global_start = min(all_dates)
    global_end = max(all_dates) + timedelta(days=60)

    syms_needed = list({s.ticker for s in signals if s.entry is not None})
    # Per-ticker download: pick the right interval based on data age
    price_data: dict[str, Any] = {}
    for sym in syms_needed:
        dl_start = global_start.isoformat()
        dl_end = min(global_end, today + timedelta(days=1)).isoformat()

        # If interval has a max lookback and global_start is too old, fall back to daily
        days_back = (today - global_start).days
        effective_interval = interval if days_back <= max_days else "1d"

        df = _download_bars(sym, dl_start, dl_end, effective_interval)
        # If intraday failed, retry with daily
        if df is None and effective_interval != "1d":
            df = _download_bars(sym, dl_start, dl_end, "1d")
        price_data[sym] = df

    trades: list[SignalTrade] = []
    wins = losses = open_trades = tradeable = 0
    total_pnl = 0.0
    rr_list: list[float] = []

    for sig in signals:
        if sig.entry is None:
            trades.append(SignalTrade(
                signal_id=sig.id, ticker=sig.ticker, side=sig.side,
                signal_date=sig.created_at.isoformat(), entry_price=0.0,
                stop=None, first_target=None, exit_price=None, exit_date=None,
                outcome="no_entry", pnl=0.0, qty=qty, rr_ratio=None,
            ))
            continue

        tradeable += 1
        entry = _f(sig.entry)
        stop = _f(sig.stop)
        ft = _parse_first_target(sig)

        if entry is None:
            continue

        rr: Optional[float] = None
        if stop is not None and ft is not None and entry != stop:
            risk = abs(entry - stop)
            reward = abs(ft - entry)
            rr = round(reward / risk, 2)
            rr_list.append(rr)

        outcome, exit_price, exit_date = _simulate(
            sig.side, entry, stop, ft,
            price_data.get(sig.ticker), sig.created_at.date(),
        )

        pnl = 0.0
        if exit_price is not None:
            direction = 1.0 if sig.side.upper() == "BUY" else -1.0
            pnl = (exit_price - entry) * direction * qty
            total_pnl += pnl
            if outcome == "win":
                wins += 1
            else:
                losses += 1
        elif outcome == "open":
            open_trades += 1

        trades.append(SignalTrade(
            signal_id=sig.id, ticker=sig.ticker, side=sig.side,
            signal_date=sig.created_at.isoformat(), entry_price=entry,
            stop=stop, first_target=ft, exit_price=exit_price,
            exit_date=exit_date, outcome=outcome, pnl=round(pnl, 2),
            qty=qty, rr_ratio=rr,
        ))

    simulated = wins + losses
    return SignalBacktestResult(
        start=start or "", end=end or "", ticker_filter=ticker,
        total_signals=len(signals), tradeable=tradeable,
        wins=wins, losses=losses, open_trades=open_trades,
        win_rate_pct=round(wins / simulated * 100, 1) if simulated > 0 else 0.0,
        total_pnl=round(total_pnl, 2),
        avg_rr=round(sum(rr_list) / len(rr_list), 2) if rr_list else None,
        trades=trades,
    )
