from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import logging
from typing import Any

from sqlmodel import Session, delete, select

from app.config import settings
from app.models import Execution, Order, PnL, Position
from broker import get_broker

log = logging.getLogger(__name__)

_TERMINAL_FILLED_STATUSES = {"FILLED"}


def sync_orders(session: Session) -> list[Order]:
    rows = session.exec(select(Order).order_by(Order.created_at.desc())).all()
    brokers: dict[tuple[str, str], Any] = {}

    for row in rows:
        if not row.order_id:
            continue
        key = (row.broker, row.broker_env)
        broker = brokers.get(key)
        if broker is None:
            try:
                broker = get_broker(broker_name=row.broker, broker_env=row.broker_env)
            except Exception as exc:
                log.warning("broker unavailable for order id=%s: %s", row.id, exc)
                continue
            brokers[key] = broker
        try:
            synced = broker.sync_order(row.order_id)
            if not synced:
                continue
            row.status = synced.get("status", row.status)
            row.reason = synced.get("reason")
            synced_price = synced.get("price")
            if synced_price is not None:
                row.price = float(synced_price)
            synced_qty = synced.get("qty")
            if synced_qty is not None:
                row.qty = float(synced_qty)
        except Exception as exc:
            log.warning(
                "failed to sync order id=%s broker=%s env=%s: %s",
                row.order_id,
                row.broker,
                row.broker_env,
                exc,
            )

    session.commit()
    for row in rows:
        session.refresh(row)
    return rows


def sync_executions(session: Session) -> list[Execution]:
    filled_orders = session.exec(select(Order).where(Order.status.in_(_TERMINAL_FILLED_STATUSES))).all()
    existing_order_ids = {
        execution.order_id
        for execution in session.exec(select(Execution)).all()
    }

    for order in filled_orders:
        if order.id is None or order.id in existing_order_ids:
            continue
        if order.price is None:
            continue
        session.add(
            Execution(
                order_id=order.id,
                ticker=order.ticker,
                side=order.side,
                qty=order.qty,
                price=order.price,
                broker_env=order.broker_env,
            )
        )

    session.commit()
    return session.exec(select(Execution).order_by(Execution.executed_at.desc())).all()


def sync_positions(session: Session, broker_name: str | None = None, broker_env: str | None = None) -> list[Position]:
    resolved_name = broker_name or settings.broker
    resolved_env = (broker_env or _primary_sync_env()).upper()
    try:
        broker = get_broker(broker_name=resolved_name, broker_env=resolved_env)
        # Use per-account-type fetch when available (moomoo); fall back to single-account
        fetch_by_type = getattr(broker, "positions_by_type", None)
        if callable(fetch_by_type):
            positions_map = fetch_by_type()  # {acc_type: {ticker: {qty, avg_price}}}
        else:
            positions_map = {"MARGIN": broker.positions()}
    except Exception as exc:
        log.warning("position sync skipped env=%s: %s", resolved_env, exc)
        return session.exec(
            select(Position).where(Position.broker_env == resolved_env).order_by(Position.ticker.asc())
        ).all()

    session.exec(delete(Position).where(Position.broker_env == resolved_env))
    for acc_type, positions in positions_map.items():
        for ticker, data in positions.items():
            session.add(
                Position(
                    ticker=ticker,
                    qty=float(data.get("qty", 0.0)),
                    avg_price=float(data.get("avg_price", 0.0)),
                    broker_env=resolved_env,
                    acc_type=acc_type,
                )
            )

    session.commit()
    return session.exec(select(Position).where(Position.broker_env == resolved_env).order_by(Position.ticker.asc())).all()


def sync_pnl(session: Session, broker_name: str | None = None, broker_env: str | None = None) -> list[PnL]:
    resolved_name = broker_name or settings.broker
    resolved_env = (broker_env or _primary_sync_env()).upper()
    try:
        broker = get_broker(broker_name=resolved_name, broker_env=resolved_env)
    except Exception as exc:
        log.warning("pnl sync skipped (broker unavailable) env=%s: %s", resolved_env, exc)
        return session.exec(select(PnL).where(PnL.broker_env == resolved_env).order_by(PnL.date.asc())).all()
    executions = session.exec(
        select(Execution)
        .where(Execution.broker_env == resolved_env)
        .order_by(Execution.executed_at.asc())
    ).all()

    realized_by_date: dict[str, float] = defaultdict(float)
    inventory: dict[str, dict[str, float]] = {}

    for execution in executions:
        ticker_state = inventory.setdefault(execution.ticker, {"qty": 0.0, "avg_price": 0.0})
        side = execution.side.upper()
        qty = float(execution.qty)
        price = float(execution.price)
        exec_date = execution.executed_at.date().isoformat()

        if side == "BUY":
            remaining = qty

            # First cover any existing short position.
            if ticker_state["qty"] < 0:
                cover_qty = min(remaining, abs(ticker_state["qty"]))
                realized_by_date[exec_date] += (ticker_state["avg_price"] - price) * cover_qty
                ticker_state["qty"] += cover_qty
                remaining -= cover_qty
                if ticker_state["qty"] == 0:
                    ticker_state["avg_price"] = 0.0

            # Any leftover opens/increases a long position.
            if remaining > 0:
                if ticker_state["qty"] > 0:
                    total_cost = ticker_state["qty"] * ticker_state["avg_price"] + remaining * price
                    ticker_state["qty"] += remaining
                    ticker_state["avg_price"] = total_cost / ticker_state["qty"]
                else:
                    ticker_state["qty"] = remaining
                    ticker_state["avg_price"] = price
            continue

        if side == "SELL":
            remaining = qty

            # First close any existing long position.
            if ticker_state["qty"] > 0:
                close_qty = min(remaining, ticker_state["qty"])
                realized_by_date[exec_date] += (price - ticker_state["avg_price"]) * close_qty
                ticker_state["qty"] -= close_qty
                remaining -= close_qty
                if ticker_state["qty"] == 0:
                    ticker_state["avg_price"] = 0.0

            # Any leftover opens/increases a short position.
            if remaining > 0:
                short_size = abs(min(ticker_state["qty"], 0.0))
                if short_size > 0:
                    total_proceeds = short_size * ticker_state["avg_price"] + remaining * price
                    new_short_size = short_size + remaining
                    ticker_state["qty"] = -new_short_size
                    ticker_state["avg_price"] = total_proceeds / new_short_size
                else:
                    ticker_state["qty"] = -remaining
                    ticker_state["avg_price"] = price
            continue

    unrealized_total = 0.0
    quote_last_price = getattr(broker, "quote_last_price", None)
    if callable(quote_last_price):
        for position in session.exec(select(Position).where(Position.broker_env == resolved_env)).all():
            try:
                last_price = float(quote_last_price(position.ticker))
                if position.qty >= 0:
                    unrealized_total += (last_price - position.avg_price) * position.qty
                else:
                    unrealized_total += (position.avg_price - last_price) * abs(position.qty)
            except Exception as exc:
                log.warning("failed to refresh quote for pnl sync ticker=%s: %s", position.ticker, exc)

    session.exec(delete(PnL).where(PnL.broker_env == resolved_env))

    pnl_dates = sorted(realized_by_date)
    for date_key in pnl_dates:
        session.add(PnL(date=date_key, realized=realized_by_date[date_key], unrealized=0.0, broker_env=resolved_env))

    today_key = datetime.now().date().isoformat()
    if pnl_dates and today_key == pnl_dates[-1]:
        latest = session.exec(select(PnL).where(PnL.date == today_key, PnL.broker_env == resolved_env)).first()
        if latest:
            latest.unrealized = unrealized_total
    else:
        session.add(PnL(date=today_key, realized=0.0, unrealized=unrealized_total, broker_env=resolved_env))

    session.commit()
    return session.exec(select(PnL).where(PnL.broker_env == resolved_env).order_by(PnL.date.asc())).all()


def sync_trading_state(
    session: Session,
    broker_name: str | None = None,
    broker_env: str | None = None,
) -> dict[str, list[Any]]:
    sync_orders(session)
    sync_executions(session)
    sync_positions(session, broker_name=broker_name, broker_env=broker_env)
    sync_pnl(session, broker_name=broker_name, broker_env=broker_env)
    return {
        "orders": session.exec(select(Order).order_by(Order.created_at.desc())).all(),
        "executions": session.exec(select(Execution).order_by(Execution.executed_at.desc())).all(),
        "positions": session.exec(select(Position).order_by(Position.ticker.asc())).all(),
        "pnls": session.exec(select(PnL).order_by(PnL.date.asc())).all(),
    }


def _primary_sync_env() -> str:
    candidates = [
        settings.twitter_broker_env.upper(),
        settings.broker_env.upper(),
        settings.dexter_broker_env.upper(),
    ]
    for candidate in candidates:
        if candidate == "REAL":
            return candidate
    return candidates[0]
