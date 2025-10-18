import logging
from typing import Any, Dict, Optional

import pandas as pd
from futu import ModifyOrderOp, OpenUSTradeContext, OrderStatus, OrderType, RET_OK, TimeInForce, TrdEnv, TrdSide

from .base import Broker

log = logging.getLogger(__name__)

_ENV_MAP: Dict[str, TrdEnv] = {
    "SIMULATE": TrdEnv.SIMULATE,
    "REAL": TrdEnv.REAL,
}

_SIDE_MAP: Dict[str, TrdSide] = {
    "BUY": TrdSide.BUY,
    "SELL": TrdSide.SELL,
}

_ORDER_TYPE_MAP: Dict[str, OrderType] = {
    "LIMIT": OrderType.NORMAL,
    "MARKET": OrderType.MARKET,
}

_TIF_MAP: Dict[str, TimeInForce] = {
    "DAY": TimeInForce.DAY,
    "GTC": TimeInForce.GTC,
}

_ORDER_STATUS_MAP: Dict[str, str] = {
    "SUBMITTED": "NEW",
    "SUBMITTING": "NEW",
    "WAITING_SUBMIT": "NEW",
    "PENDING_SUBMIT": "NEW",
    "FILLED_PART": "PARTIALLY_FILLED",
    "FILLED_ALL": "FILLED",
    "CANCELLED_PART": "PARTIALLY_CANCELED",
    "CANCELLED_ALL": "CANCELED",
    "FAILED": "REJECTED",
    "REJECTED": "REJECTED",
}

_CANCELABLE_STATUSES = [
    OrderStatus.SUBMITTED,
    OrderStatus.SUBMITTING,
    OrderStatus.WAITING_SUBMIT,
    OrderStatus.FILLED_PART,
]


class MoomooBroker(Broker):
    name = "moomoo"

    def __init__(self, host: str, port: int, trd_env: str, acc_id: Optional[int] = None):
        self._host = host
        self._port = port
        self._trd_env = self._parse_env(trd_env)
        self._ctx = self._connect()
        self._acc_id = self._initialise_account(acc_id)

    # --------------------------------------------------------------------- #
    # Lifecycle helpers
    # --------------------------------------------------------------------- #
    def _parse_env(self, env: str) -> TrdEnv:
        try:
            return _ENV_MAP[env.upper()]
        except KeyError as exc:
            raise ValueError(f"Unsupported trade environment '{env}'. Use SIMULATE or REAL.") from exc

    def _connect(self) -> OpenUSTradeContext:
        try:
            ctx = OpenUSTradeContext(host=self._host, port=self._port)
        except Exception as exc:  # pragma: no cover - SDK raises varied exceptions
            log.exception("Failed to connect to Moomoo OpenD at %s:%s", self._host, self._port)
            raise RuntimeError("Unable to connect to Moomoo OpenD") from exc
        log.info("Connected to Moomoo OpenD at %s:%s", self._host, self._port)
        return ctx

    def _initialise_account(self, requested_acc_id: Optional[int]) -> int:
        ret, acc_df = self._ctx.get_acc_list()
        if ret != RET_OK:
            msg = acc_df if isinstance(acc_df, str) else "Unknown error"
            log.error("Failed to fetch Moomoo account list: %s", msg)
            raise RuntimeError(f"Failed to fetch Moomoo account list: {msg}")
        if acc_df.empty:
            raise RuntimeError("No Moomoo trading accounts available for the requested environment.")
        target_env = str(self._trd_env).upper()
        env_col = acc_df.get("trd_env")
        if env_col is not None:
            acc_df = acc_df[env_col.astype(str).str.upper() == target_env]
        if acc_df.empty:
            raise RuntimeError(f"No Moomoo accounts available for environment {target_env}.")
        if "acc_id" in acc_df.columns:
            available_ids = [int(v) for v in acc_df["acc_id"] if not pd.isna(v)]
        elif "acc_index" in acc_df.columns:
            available_ids = [int(v) for v in acc_df["acc_index"] if not pd.isna(v)]
        else:
            available_ids = []
        if not available_ids:
            raise RuntimeError("Could not determine account identifiers from Moomoo response.")
        if requested_acc_id is not None:
            if requested_acc_id not in available_ids:
                raise RuntimeError(
                    f"Requested Moomoo account {requested_acc_id} not found. Available accounts: {available_ids}"
                )
            selected = requested_acc_id
        else:
            selected = available_ids[0]
        log.info(
            "Using Moomoo account %s in %s environment",
            selected,
            target_env,
        )
        return selected

    def close(self) -> None:
        try:
            self._ctx.close()
        except Exception:  # pragma: no cover - best effort close
            log.debug("Failed to close Moomoo trade context cleanly.", exc_info=True)

    def __del__(self) -> None:  # pragma: no cover - destructor path hard to test
        self.close()

    # --------------------------------------------------------------------- #
    # Utility
    # --------------------------------------------------------------------- #
    def _normalise_symbol(self, ticker: str) -> str:
        if "." in ticker:
            return ticker
        return f"US.{ticker}"

    def _strip_symbol(self, code: str) -> str:
        return code.split(".", 1)[-1] if "." in code else code

    def _normalise_status(self, status: str) -> str:
        upper_status = status.upper()
        return _ORDER_STATUS_MAP.get(upper_status, upper_status)

    def _build_order_payload(
        self,
        ticker: str,
        side: str,
        qty: float,
        price: Optional[float],
        order_type: str,
        tif: str,
    ) -> Dict[str, Any]:
        futu_side = _SIDE_MAP.get(side.upper())
        if futu_side is None:
            raise ValueError(f"Unsupported order side '{side}'. Expected BUY or SELL.")
        futu_order_type = _ORDER_TYPE_MAP.get(order_type.upper())
        if futu_order_type is None:
            raise ValueError(f"Unsupported order type '{order_type}'. Expected LIMIT or MARKET.")
        futu_tif = _TIF_MAP.get(tif.upper())
        if futu_tif is None:
            raise ValueError(f"Unsupported time-in-force '{tif}'. Expected DAY, GTC, or IOC.")
        if futu_order_type == OrderType.NORMAL and price is None:
            raise ValueError("Limit orders require a price.")
        return {
            "price": price or 0.0,
            "qty": qty,
            "code": self._normalise_symbol(ticker),
            "side": futu_side,
            "order_type": futu_order_type,
            "tif": futu_tif,
        }

    def _format_order_response(
        self,
        resp_row: Dict[str, Any],
        fallback_ticker: str,
        fallback_side: str,
        fallback_qty: float,
        fallback_price: Optional[float],
    ) -> Dict[str, Any]:
        order_status = str(resp_row.get("order_status", "")).upper()
        last_err = resp_row.get("last_err_msg") or None
        price = resp_row.get("price") or resp_row.get("dealt_avg_price") or fallback_price
        qty = resp_row.get("qty") or resp_row.get("qty_all") or fallback_qty
        return {
            "broker": self.name,
            "ticker": self._strip_symbol(str(resp_row.get("code", fallback_ticker))),
            "side": str(resp_row.get("trd_side", fallback_side)).upper(),
            "qty": float(qty) if qty is not None else None,
            "price": float(price) if price is not None else None,
            "status": self._normalise_status(order_status),
            "reason": last_err,
            "order_id": str(resp_row.get("order_id")) if resp_row.get("order_id") is not None else None,
        }

    # --------------------------------------------------------------------- #
    # Broker interface
    # --------------------------------------------------------------------- #
    def place_order(
        self,
        ticker: str,
        side: str,
        qty: float,
        price: Optional[float] = None,
        order_type: str = "LIMIT",
        tif: str = "DAY",
    ) -> Dict[str, Any]:
        payload = self._build_order_payload(ticker, side, qty, price, order_type, tif)
        log.debug(
            "Placing order via Moomoo: %s %s %s qty=%s price=%s type=%s tif=%s",
            payload["code"],
            side,
            self._trd_env,
            qty,
            price,
            order_type,
            tif,
        )
        ret, data = self._ctx.place_order(
            payload["price"],
            payload["qty"],
            payload["code"],
            payload["side"],
            order_type=payload["order_type"],
            time_in_force=payload["tif"],
            trd_env=self._trd_env,
            acc_id=self._acc_id,
        )
        if ret != RET_OK:
            msg = data if isinstance(data, str) else "Unknown error"
            log.error("Failed to place order with Moomoo: %s", msg)
            raise RuntimeError(f"Moomoo order placement failed: {msg}")
        resp_row = data.iloc[0].to_dict() if not data.empty else {}
        order_summary = self._format_order_response(
            resp_row,
            fallback_ticker=ticker,
            fallback_side=side,
            fallback_qty=qty,
            fallback_price=price,
        )
        log.info("Order submitted to Moomoo: id=%s status=%s", order_summary.get("order_id"), order_summary["status"])
        return order_summary

    def positions(self) -> Dict[str, Dict[str, Any]]:
        ret, data = self._ctx.position_list_query(trd_env=self._trd_env, acc_id=self._acc_id)
        if ret != RET_OK:
            msg = data if isinstance(data, str) else "Unknown error"
            log.error("Failed to fetch positions from Moomoo: %s", msg)
            raise RuntimeError(f"Moomoo positions retrieval failed: {msg}")
        if data.empty:
            return {}
        positions: Dict[str, Dict[str, Any]] = {}
        for _, row in data.iterrows():
            code = str(row.get("code", ""))
            ticker = self._strip_symbol(code)
            qty = float(row.get("qty", 0.0))
            avg_price = float(row.get("cost_price", 0.0))
            positions[ticker] = {"qty": qty, "avg_price": avg_price}
        log.debug("Fetched %d positions from Moomoo", len(positions))
        return positions

    def cancel_all(self) -> None:
        ret, data = self._ctx.order_list_query(
            trd_env=self._trd_env,
            acc_id=self._acc_id,
            status_filter_list=_CANCELABLE_STATUSES,
        )
        if ret != RET_OK:
            msg = data if isinstance(data, str) else "Unknown error"
            log.error("Failed to query open orders for cancellation: %s", msg)
            raise RuntimeError(f"Moomoo order query failed: {msg}")
        if data.empty:
            log.info("No open Moomoo orders to cancel.")
            return
        for _, row in data.iterrows():
            order_id = row.get("order_id")
            if order_id is None:
                continue
            ret, err = self._ctx.modify_order(
                ModifyOrderOp.CANCEL,
                order_id=order_id,
                trd_env=self._trd_env,
                acc_id=self._acc_id,
            )
            if ret != RET_OK:
                log.warning("Failed to cancel order %s: %s", order_id, err)
            else:
                log.info("Cancelled Moomoo order %s", order_id)
