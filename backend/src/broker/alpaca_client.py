"""Alpaca Markets broker implementation.

Uses the ``alpaca-py`` SDK to communicate with Alpaca's REST / WebSocket API.
No local gateway process is required — authentication is handled via API keys.
"""

import logging
from typing import Any, Dict, Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, OrderStatus, OrderType, TimeInForce
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
)

from .base import Broker

log = logging.getLogger(__name__)

_SIDE_MAP: Dict[str, OrderSide] = {
    "BUY": OrderSide.BUY,
    "SELL": OrderSide.SELL,
}

_TIF_MAP: Dict[str, TimeInForce] = {
    "DAY": TimeInForce.DAY,
    "GTC": TimeInForce.GTC,
    "IOC": TimeInForce.IOC,
    "FOK": TimeInForce.FOK,
}

_STATUS_MAP: Dict[str, str] = {
    "new": "NEW",
    "partially_filled": "PARTIALLY_FILLED",
    "filled": "FILLED",
    "done_for_day": "DONE_FOR_DAY",
    "canceled": "CANCELED",
    "expired": "EXPIRED",
    "replaced": "REPLACED",
    "pending_cancel": "PENDING_CANCEL",
    "pending_replace": "PENDING_REPLACE",
    "accepted": "NEW",
    "pending_new": "NEW",
    "accepted_for_bidding": "NEW",
    "stopped": "STOPPED",
    "rejected": "REJECTED",
    "suspended": "SUSPENDED",
    "calculated": "CALCULATED",
}


class AlpacaBroker(Broker):
    """Broker backed by Alpaca Markets REST API."""

    name = "alpaca"

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        paper: bool = True,
    ):
        self._paper = paper
        self._client = TradingClient(
            api_key=api_key,
            secret_key=secret_key,
            paper=paper,
        )
        mode = "paper" if paper else "live"
        log.info("Alpaca broker initialised (%s mode)", mode)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalise_symbol(ticker: str) -> str:
        """Strip market prefix (e.g. ``US.AAPL`` → ``AAPL``)."""
        return ticker.split(".")[-1].upper()

    @staticmethod
    def _normalise_status(status: str) -> str:
        return _STATUS_MAP.get(status.lower(), status.upper())

    def _format_order(self, order: Any) -> Dict[str, Any]:
        return {
            "broker": self.name,
            "ticker": order.symbol,
            "side": str(order.side).upper(),
            "qty": float(order.qty) if order.qty else None,
            "price": float(order.limit_price) if order.limit_price else None,
            "status": self._normalise_status(str(order.status)),
            "reason": None,
            "order_id": str(order.id),
        }

    # ------------------------------------------------------------------ #
    # Broker interface
    # ------------------------------------------------------------------ #
    def place_order(
        self,
        ticker: str,
        side: str,
        qty: float,
        price: Optional[float] = None,
        order_type: str = "LIMIT",
        tif: str = "DAY",
    ) -> Dict[str, Any]:
        symbol = self._normalise_symbol(ticker)
        alpaca_side = _SIDE_MAP.get(side.upper())
        if alpaca_side is None:
            raise ValueError(f"Unsupported order side '{side}'. Expected BUY or SELL.")
        alpaca_tif = _TIF_MAP.get(tif.upper())
        if alpaca_tif is None:
            raise ValueError(f"Unsupported time-in-force '{tif}'. Expected DAY, GTC, IOC, or FOK.")

        ot = order_type.upper()
        if ot == "MARKET":
            req = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=alpaca_side,
                time_in_force=alpaca_tif,
            )
        elif ot == "LIMIT":
            if price is None:
                raise ValueError("Limit orders require a price.")
            req = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=alpaca_side,
                time_in_force=alpaca_tif,
                limit_price=price,
            )
        else:
            raise ValueError(f"Unsupported order type '{order_type}'. Expected LIMIT or MARKET.")

        log.debug(
            "Placing Alpaca order: %s %s qty=%s price=%s type=%s tif=%s",
            symbol, side, qty, price, order_type, tif,
        )
        order = self._client.submit_order(req)
        result = self._format_order(order)
        log.info("Alpaca order submitted: id=%s status=%s", result["order_id"], result["status"])
        return result

    def positions(self) -> Dict[str, Dict[str, Any]]:
        raw = self._client.get_all_positions()
        positions: Dict[str, Dict[str, Any]] = {}
        for pos in raw:
            positions[pos.symbol] = {
                "qty": float(pos.qty),
                "avg_price": float(pos.avg_entry_price),
            }
        log.debug("Fetched %d positions from Alpaca", len(positions))
        return positions

    def account(self) -> Dict[str, Any]:
        """Return account summary (balance, buying power, etc.)."""
        acct = self._client.get_account()
        return {
            "id": str(acct.id),
            "status": str(acct.status),
            "currency": acct.currency,
            "cash": float(acct.cash),
            "portfolio_value": float(acct.portfolio_value) if acct.portfolio_value else 0.0,
            "buying_power": float(acct.buying_power),
            "equity": float(acct.equity),
            "pattern_day_trader": acct.pattern_day_trader,
            "trading_blocked": acct.trading_blocked,
            "account_blocked": acct.account_blocked,
        }

    def cancel_all(self) -> None:
        statuses = self._client.cancel_orders()
        log.info("Alpaca cancel_all: %d cancel requests sent", len(statuses))
