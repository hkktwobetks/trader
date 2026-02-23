## Broker Integration

This project supports multiple brokers via an abstraction layer (`src/broker/base.py`).
Set the `BROKER` environment variable to choose one: `paper` or `alpaca`.

---

### Alpaca (recommended)

Alpaca provides a REST API — no local gateway process required.

#### Setup
1. Create an account at [alpaca.markets](https://alpaca.markets/)
2. Generate API keys from the dashboard (Paper Trading keys for testing)
3. Set environment variables:

```bash
BROKER=alpaca
ALPACA_API_KEY=PKxxxxxxxxxxxxxxxxxxxx
ALPACA_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ALPACA_PAPER=true    # set to false for live trading
```

#### Features
- US stocks, ETFs, options, crypto
- Commission-free trading
- Paper trading with instant setup
- REST + WebSocket API (no gateway daemon needed)

#### Quick test
```bash
cd backend
pip install -r requirements.txt
python -c "
from alpaca.trading.client import TradingClient
c = TradingClient('YOUR_KEY', 'YOUR_SECRET', paper=True)
print(c.get_account())
"
```

---

### Interactive Brokers (IBKR) — future option

> 📝 **Memo:** IBKR is the most full-featured option for multi-market trading.

#### Pros
- 150+ markets, 33 countries (US, JP, HK, EU stocks, options, futures, FX)
- TWS API / Web API
- Japanese residents can open accounts (IBSJ)
- Advanced order types (TWAP, VWAP, algo orders)

#### Cons
- Requires TWS or IB Gateway process to be running (similar to OpenD)
- More complex setup
- Commission per trade ($0.0035/share)

#### Implementation notes
- Python SDK: `ib_insync` (high-level) or `ibapi` (official)
- Would need a new `broker/ibkr_client.py` implementing `Broker` base class
- IB Gateway would need its own Docker service (similar to opend)
- Reference: [interactivebrokers.com/api](https://www.interactivebrokers.com/en/trading/ib-api.php)
