from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

log = logging.getLogger(__name__)


def send_line(message: str) -> None:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    user_id = os.getenv("LINE_USER_ID", "")
    if not token or not user_id:
        return
    try:
        httpx.post(
            "https://api.line.me/v2/bot/message/push",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"to": user_id, "messages": [{"type": "text", "text": message}]},
            timeout=10,
        )
    except Exception as e:
        log.warning("LINE notify failed: %s", e)


def notify_signal(
    *,
    source: str,
    ticker: str,
    side: str,
    entry: Optional[float],
    stop: Optional[float],
    targets: list[float],
    broker_env: str,
    acc_type: str = "auto",
    # 価格シフト
    shift_delta: Optional[float] = None,
    original_entry: Optional[float] = None,
    # スキップ
    skipped: bool = False,
    skip_reason: str = "",
    # 発注済み
    order_placed: bool = False,
    order_status: str = "",
    # 自動発注ブロック理由（auto_trade=OFF / confidence 不足など）
    blocked_reason: Optional[str] = None,
    # 一部利確の割合（0-1）
    exit_fraction: Optional[float] = None,
) -> None:
    is_exit = side.upper() == "SELL"
    side_arrow = "🔼" if side.upper() == "BUY" else ("💰" if is_exit else "🔽")
    env_tag = f"[{broker_env}]" + (f"({acc_type})" if broker_env == "REAL" and acc_type not in ("auto", "") else "")

    if is_exit and exit_fraction is not None and exit_fraction < 1.0:
        action_label = f"EXIT {int(exit_fraction * 100)}%"
    elif is_exit:
        action_label = "EXIT"
    else:
        action_label = side.upper()
    lines = [f"{side_arrow} {source.upper()} | {ticker} {action_label} {env_tag}"]

    if not is_exit:
        if entry is not None:
            if shift_delta is not None and original_entry is not None:
                lines.append(f"Entry : ${original_entry:.2f} → ${entry:.2f} (shift {shift_delta:+.2f})")
            else:
                lines.append(f"Entry : ${entry:.2f}")
        if stop is not None:
            lines.append(f"Stop  : ${stop:.2f}")
        if targets:
            lines.append("Target: " + " / ".join(f"${t:.2f}" for t in targets))

    if skipped:
        lines.append(f"⚠️ SKIP — {skip_reason}")
    elif order_placed:
        if is_exit and exit_fraction is not None and exit_fraction < 1.0:
            status_label = f"{int(exit_fraction * 100)}%利確発注済み"
        elif is_exit:
            status_label = "全量利確発注済み"
        else:
            status_label = "発注済み"
        lines.append(f"✅ {status_label} ({order_status})")
    elif blocked_reason:
        lines.append(f"📋 シグナル受信（{blocked_reason}）")
    else:
        lines.append("📋 シグナル受信")

    send_line("\n".join(lines))
