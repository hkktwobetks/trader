"""
Persistent OpenQuoteContext that listens for moomoo price reminder pushes
and sends LINE notifications when SL/TP levels are hit.
"""
from __future__ import annotations

import logging
import threading
import time

from app.line_notify import send_line as _send_line
from moomoo import OpenQuoteContext, PriceReminderHandlerBase, RET_OK

log = logging.getLogger(__name__)


class _PriceReminderHandler(PriceReminderHandlerBase):
    def on_recv_rsp(self, rsp_pb):
        ret, content = super().on_recv_rsp(rsp_pb)
        if ret != RET_OK or content is None:
            return ret, content
        try:
            row = {}
            if hasattr(content, "iloc"):
                row = content.iloc[0].to_dict()
            elif hasattr(content, "to_dict"):
                row = content.to_dict()
            elif isinstance(content, dict):
                row = content

            code = str(row.get("stock_code") or row.get("code", ""))
            ticker = code.split(".")[-1] if "." in code else code
            note = str(row.get("note", ""))
            cur_price = row.get("cur_price") or row.get("last_price", "")
            reminder_type = str(row.get("reminder_type", ""))

            icon = "🔴" if "DOWN" in reminder_type.upper() else "🟢"
            lines = [f"{icon} 価格アラート: {ticker}"]
            if note:
                lines.append(note)
            lines.append(f"現在値: {cur_price}")
            _send_line("\n".join(lines))
            log.info("Price reminder fired: %s note=%s price=%s", ticker, note, cur_price)
        except Exception as e:
            log.warning("Failed to process price reminder push: %s", e)
        return ret, content


class PriceReminderWorker:
    def __init__(self, host: str, port: int, is_encrypt: bool = False):
        self._host = host
        self._port = port
        self._is_encrypt = is_encrypt
        self._ctx: OpenQuoteContext | None = None
        self._lock = threading.Lock()
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        t = threading.Thread(target=self._run, daemon=True, name="price-reminder-worker")
        t.start()
        log.info("PriceReminderWorker started (host=%s port=%s)", self._host, self._port)

    def _connect(self) -> OpenQuoteContext:
        ctx = OpenQuoteContext(host=self._host, port=self._port, is_encrypt=self._is_encrypt)
        ctx.set_handler(_PriceReminderHandler())
        ctx.start()
        return ctx

    def _run(self) -> None:
        while self._running:
            try:
                with self._lock:
                    if self._ctx is None:
                        self._ctx = self._connect()
                        log.info("PriceReminderWorker: quote context connected")
                time.sleep(30)
            except Exception as e:
                log.warning("PriceReminderWorker error, reconnecting in 10s: %s", e)
                with self._lock:
                    if self._ctx is not None:
                        try:
                            self._ctx.close()
                        except Exception:
                            pass
                        self._ctx = None
                time.sleep(10)

    def stop(self) -> None:
        self._running = False
        with self._lock:
            if self._ctx is not None:
                try:
                    self._ctx.stop()
                    self._ctx.close()
                except Exception:
                    pass
                self._ctx = None


_worker: PriceReminderWorker | None = None


def init_worker(host: str, port: int, is_encrypt: bool = False) -> PriceReminderWorker:
    global _worker
    if _worker is None:
        _worker = PriceReminderWorker(host, port, is_encrypt)
    return _worker


def get_worker() -> PriceReminderWorker | None:
    return _worker
