#!/usr/bin/env python3
"""Smoke test for Alpaca Trading API.

Usage:
    # Set env vars first:
    #   export ALPACA_API_KEY=PKxxxxxxxxx
    #   export ALPACA_SECRET_KEY=xxxxxxxxx
    #
    # Or create a .env file with those values.

    python scripts/smoke_alpaca.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest


def main():
    api_key = os.getenv("ALPACA_API_KEY", "")
    secret_key = os.getenv("ALPACA_SECRET_KEY", "")
    paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"

    if not api_key or api_key == "your_alpaca_api_key":
        print("❌ ALPACA_API_KEY is not set. Please set it in .env or environment.")
        sys.exit(1)
    if not secret_key or secret_key == "your_alpaca_secret_key":
        print("❌ ALPACA_SECRET_KEY is not set. Please set it in .env or environment.")
        sys.exit(1)

    mode = "paper" if paper else "LIVE"
    print(f"🔌 Connecting to Alpaca ({mode} mode)...")

    client = TradingClient(api_key=api_key, secret_key=secret_key, paper=paper)

    # 1. Account info
    print("\n📊 Account Info:")
    account = client.get_account()
    print(f"  Account ID:     {account.id}")
    print(f"  Status:         {account.status}")
    print(f"  Currency:       {account.currency}")
    print(f"  Cash:           ${float(account.cash):,.2f}")
    print(f"  Buying Power:   ${float(account.buying_power):,.2f}")
    print(f"  Portfolio Value: ${float(account.portfolio_value):,.2f}")
    print(f"  Equity:         ${float(account.equity):,.2f}")
    print(f"  Day Trading:    {account.pattern_day_trader}")
    print(f"  Trading Blocked: {account.trading_blocked}")

    # 2. Positions
    print("\n📈 Current Positions:")
    positions = client.get_all_positions()
    if not positions:
        print("  (no positions)")
    else:
        for pos in positions:
            print(f"  {pos.symbol}: {pos.qty} shares @ ${float(pos.avg_entry_price):.2f}")

    # 3. Submit a test limit buy (very low price so it won't fill)
    print("\n🧪 Submitting test limit order: BUY 1 AAPL @ $1.00 ...")
    try:
        order = client.submit_order(
            LimitOrderRequest(
                symbol="AAPL",
                qty=1,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                limit_price=1.00,
            )
        )
        print(f"  ✅ Order submitted: id={order.id} status={order.status}")
    except Exception as e:
        print(f"  ❌ Order failed: {e}")
        return

    # 4. List open orders
    print("\n📋 Open Orders:")
    open_orders = client.get_orders(
        filter=GetOrdersRequest(status=QueryOrderStatus.OPEN)
    )
    for o in open_orders:
        print(f"  {o.id}: {o.side} {o.qty} {o.symbol} @ {o.limit_price} [{o.status}]")

    # 5. Cancel all open orders
    print("\n🗑️  Cancelling all open orders...")
    cancel_statuses = client.cancel_orders()
    print(f"  Cancelled {len(cancel_statuses)} order(s)")

    print("\n✅ Smoke test completed successfully!")


if __name__ == "__main__":
    main()
