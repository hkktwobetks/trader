from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import pandas as pd
from moomoo import (
    ModifyOrderOp,
    OpenQuoteContext,
    OpenSecTradeContext,
    OrderStatus,
    OrderType,
    RET_OK,
    SubType,
    TimeInForce,
    TrdEnv,
    TrdMarket,
    TrdSide,
    SecurityFirm,
)

from .base import Broker
from .moomoo_sdk import configure_sdk_encryption

log = logging.getLogger(__name__)

_ENV_MAP: Dict[str, TrdEnv] = {
    "SIMULATE": TrdEnv.SIMULATE,
    "REAL": TrdEnv.REAL,
}

_MARKET_MAP: Dict[str, TrdMarket] = {
    "US": TrdMarket.US,
    "JP": TrdMarket.JP,
    "HK": TrdMarket.HK,
}

_SECURITY_FIRM_MAP: Dict[str, SecurityFirm] = {
    "FUTUSECURITIES": SecurityFirm.FUTUSECURITIES,
    "FUTUINC": SecurityFirm.FUTUINC,
    "FUTUJP": SecurityFirm.FUTUJP,
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

_ACCOUNT_TYPE_PRIORITY: Dict[str, int] = {
    "MARGIN": 0,
    "CASH": 1,
    "DERIVATIVES": 2,
}

_SUPPORTED_ACCOUNT_TYPES = set(_ACCOUNT_TYPE_PRIORITY)


class MoomooBroker(Broker):
    name = "moomoo"

    def __init__(
        self,
        host: str,
        port: int,
        trd_env: str,
        rsa_private_key_path: str = "",
        acc_id: Optional[int] = None,
        market: str = "US",
        login_region: str = "",
        security_firm: str = "auto",
        preferred_acc_type: str = "auto",
        trade_password: str = "",
        trade_password_md5: str = "",
    ):
        self._host = host
        self._port = port
        self._market = (market or "US").upper()
        self._login_region = (login_region or "").strip().lower()
        self._security_firm = self._parse_security_firm(security_firm)
        self._preferred_acc_type = self._parse_preferred_acc_type(preferred_acc_type)
        self._trade_password = trade_password.strip()
        self._trade_password_md5 = trade_password_md5.strip()
        self._trd_env = self._parse_env(trd_env)
        self._rsa_private_key_path = rsa_private_key_path.strip()
        self._ctx = self._connect()
        try:
            self._unlock_trade_if_configured()
            self._acc_id = self._initialise_account(acc_id)
        except Exception:
            self._ctx.close()
            raise

    # --------------------------------------------------------------------- #
    # Lifecycle helpers
    # --------------------------------------------------------------------- #
    def _parse_env(self, env: str) -> TrdEnv:
        try:
            return _ENV_MAP[env.upper()]
        except KeyError as exc:
            raise ValueError(f"Unsupported trade environment '{env}'. Use SIMULATE or REAL.") from exc

    def _connect(self) -> OpenSecTradeContext:
        # moomoo証券（日本）などは OpenUSTradeContext ではなく Universal / Sec コンテキストが必要
        try:
            is_encrypt = configure_sdk_encryption(self._rsa_private_key_path)
            ctx = OpenSecTradeContext(
                filter_trdmarket=self._resolve_trade_market(),
                host=self._host,
                port=self._port,
                is_encrypt=is_encrypt,
                security_firm=self._security_firm,
            )
        except Exception as exc:  # pragma: no cover - SDK raises varied exceptions
            log.exception("Failed to connect to Moomoo OpenD at %s:%s", self._host, self._port)
            raise RuntimeError("Unable to connect to Moomoo OpenD") from exc
        log.info(
            "Connected to Moomoo OpenD at %s:%s market=%s security_firm=%s",
            self._host,
            self._port,
            self._market,
            self._security_firm,
        )
        return ctx

    def _quote_context(self) -> OpenQuoteContext:
        is_encrypt = configure_sdk_encryption(self._rsa_private_key_path)
        return OpenQuoteContext(host=self._host, port=self._port, is_encrypt=is_encrypt)

    def _filter_by_market_auth(self, acc_df: pd.DataFrame) -> pd.DataFrame:
        """trd_market_auth に MARKET（US/JP/HK 等）が含まれる口座に絞る。列がない・合致なしはそのまま。"""
        try:
            tm = self._resolve_trade_market()
        except ValueError:
            log.warning("Unknown MARKET=%s for Moomoo; skipping trd_market_auth filter", self._market)
            return acc_df
        col = acc_df.get("trd_market_auth")
        if col is None:
            col = acc_df.get("trdmarket_auth")
        if col is None:
            return acc_df

        def has_auth(val: Any) -> bool:
            if isinstance(val, (list, tuple)):
                if tm in val:
                    return True
                market_name = getattr(tm, "name", str(tm))
                return market_name in val or self._market in val
            return False

        filtered = acc_df[col.apply(has_auth)]
        if filtered.empty:
            log.warning(
                "No Moomoo account with trd_market_auth containing %s; using env-matched accounts only",
                self._market,
            )
            return acc_df
        return filtered

    def _resolve_trade_market(self) -> TrdMarket:
        market = _MARKET_MAP.get(self._market)
        if market is None:
            raise ValueError(f"Unsupported Moomoo market '{self._market}'.")
        return market

    def _parse_security_firm(self, security_firm: str) -> SecurityFirm:
        normalized = (security_firm or "auto").strip().upper()
        if normalized in {"", "AUTO"}:
            if self._login_region == "jp":
                return SecurityFirm.FUTUJP
            return SecurityFirm.FUTUSECURITIES
        parsed = _SECURITY_FIRM_MAP.get(normalized)
        if parsed is None:
            raise ValueError(
                f"Unsupported Moomoo security firm '{security_firm}'. "
                "Use auto, FUTUSECURITIES, FUTUINC, or FUTUJP."
            )
        return parsed

    def _parse_preferred_acc_type(self, preferred_acc_type: str) -> str | None:
        normalized = (preferred_acc_type or "auto").strip().upper()
        if normalized in {"", "AUTO"}:
            return None
        if normalized not in _SUPPORTED_ACCOUNT_TYPES:
            raise ValueError(
                f"Unsupported Moomoo account type preference '{preferred_acc_type}'. "
                "Use auto, CASH, MARGIN, or DERIVATIVES."
            )
        return normalized

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
        acc_df = self._filter_by_market_auth(acc_df)
        if acc_df.empty:
            raise RuntimeError(f"No Moomoo accounts available for environment {target_env} after market filter.")
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
            selected = self._select_best_account(acc_df, available_ids)
        log.info(
            "Using Moomoo account %s in %s environment",
            selected,
            target_env,
        )
        return selected

    def _select_best_account(self, acc_df: pd.DataFrame, available_ids: list[int]) -> int:
        candidates: list[tuple[int, int, float, int]] = []
        preferred_currency = "USD" if self._market == "US" else "JPY"
        candidate_df = acc_df

        if self._preferred_acc_type:
            filtered = acc_df[acc_df["acc_type"].astype(str).str.upper() == self._preferred_acc_type]
            if filtered.empty:
                log.warning(
                    "Requested Moomoo account type %s not found in eligible accounts; falling back to default priority.",
                    self._preferred_acc_type,
                )
            else:
                candidate_df = filtered

        for _, row in candidate_df.iterrows():
            acc_id_raw = row.get("acc_id")
            if pd.isna(acc_id_raw):
                continue
            acc_id = int(acc_id_raw)
            if acc_id not in available_ids:
                continue
            acc_type = str(row.get("acc_type", "")).upper()
            priority = _ACCOUNT_TYPE_PRIORITY.get(acc_type, 99)
            buying_power = self._query_buying_power(acc_id, preferred_currency)
            candidates.append((priority, -buying_power, acc_id, buying_power))

        if not candidates:
            return available_ids[0]

        candidates.sort()
        selected_priority, _, selected_acc_id, selected_power = candidates[0]
        log.info(
            "Selected Moomoo account %s with acc_type_priority=%s buying_power=%s currency=%s preferred_acc_type=%s",
            selected_acc_id,
            selected_priority,
            selected_power,
            preferred_currency,
            self._preferred_acc_type or "auto",
        )
        return selected_acc_id

    def _query_buying_power(self, acc_id: int, currency: str) -> float:
        try:
            ret, info = self._ctx.accinfo_query(
                trd_env=self._trd_env,
                acc_id=acc_id,
                currency=currency,
            )
            if ret != RET_OK or getattr(info, "empty", True):
                return 0.0
            row = info.iloc[0]
            value = row.get("power")
            if value in (None, "N/A"):
                value = row.get("usd_net_cash_power" if currency == "USD" else "jpy_net_cash_power")
            return float(value or 0.0)
        except Exception:
            log.warning("Failed to query buying power for Moomoo account %s", acc_id, exc_info=True)
            return 0.0

    def _unlock_trade_if_configured(self) -> None:
        if self._trd_env != TrdEnv.REAL:
            return
        if not self._trade_password and not self._trade_password_md5:
            return
        kwargs: Dict[str, Any] = {"is_unlock": True}
        if self._trade_password_md5:
            kwargs["password_md5"] = self._trade_password_md5
        else:
            kwargs["password"] = self._trade_password
        ret, data = self._ctx.unlock_trade(**kwargs)
        if ret != RET_OK:
            msg = data if isinstance(data, str) else "Unknown error"
            raise RuntimeError(f"Moomoo trade unlock failed: {msg}")
        log.info("Moomoo trade unlock succeeded for REAL environment")

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
        return f"{self._market}.{ticker}"

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
        mapped_side = _SIDE_MAP.get(side.upper())
        if mapped_side is None:
            raise ValueError(f"Unsupported order side '{side}'. Expected BUY or SELL.")
        mapped_order_type = _ORDER_TYPE_MAP.get(order_type.upper())
        if mapped_order_type is None:
            raise ValueError(f"Unsupported order type '{order_type}'. Expected LIMIT or MARKET.")
        mapped_tif = _TIF_MAP.get(tif.upper())
        if mapped_tif is None:
            raise ValueError(f"Unsupported time-in-force '{tif}'. Expected DAY, GTC, or IOC.")
        if mapped_order_type == OrderType.NORMAL and price is None:
            raise ValueError("Limit orders require a price.")
        return {
            "price": price or 0.0,
            "qty": qty,
            "code": self._normalise_symbol(ticker),
            "side": mapped_side,
            "order_type": mapped_order_type,
            "tif": mapped_tif,
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

    def quote_last_price(self, ticker: str) -> float:
        code = self._normalise_symbol(ticker)
        quote_ctx: OpenQuoteContext | None = None
        try:
            quote_ctx = self._quote_context()
            ret, data = quote_ctx.subscribe([code], [SubType.QUOTE], subscribe_push=False)
            if ret != RET_OK:
                msg = data if isinstance(data, str) else "Unknown error"
                raise RuntimeError(f"Moomoo quote subscribe failed: {msg}")
            ret, data = quote_ctx.get_stock_quote([code])
            if ret != RET_OK:
                msg = data if isinstance(data, str) else "Unknown error"
                raise RuntimeError(f"Moomoo stock quote retrieval failed: {msg}")
            if data.empty:
                raise RuntimeError(f"Moomoo stock quote returned no rows for {code}")
            row = data.iloc[0]
            price = row.get("last_price", row.get("cur_price"))
            if price is None:
                raise RuntimeError(f"Moomoo stock quote returned no last price for {code}")
            return float(price)
        finally:
            if quote_ctx is not None:
                quote_ctx.close()

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
                qty=0,
                price=0,
                trd_env=self._trd_env,
                acc_id=self._acc_id,
            )
            if ret != RET_OK:
                log.warning("Failed to cancel order %s: %s", order_id, err)
            else:
                log.info("Cancelled Moomoo order %s", order_id)

    def sync_order(self, order_id: str) -> Dict[str, Any] | None:
        ret, data = self._ctx.order_list_query(
            order_id=order_id,
            trd_env=self._trd_env,
            acc_id=self._acc_id,
        )
        if ret != RET_OK:
            msg = data if isinstance(data, str) else "Unknown error"
            raise RuntimeError(f"Moomoo order sync failed: {msg}")
        if data.empty:
            return None
        row = data.iloc[0].to_dict()
        return self._format_order_response(
            row,
            fallback_ticker=self._strip_symbol(str(row.get("code", ""))),
            fallback_side=str(row.get("trd_side", "")),
            fallback_qty=float(row.get("qty") or 0.0),
            fallback_price=float(row.get("price") or 0.0),
        )
