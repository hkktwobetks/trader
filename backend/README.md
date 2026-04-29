## Broker Integration

This project supports multiple brokers via an abstraction layer (`src/broker/base.py`).
Set the `BROKER` environment variable to choose one: `paper` or `moomoo`.

---

### Moomoo OpenD

> ⚠️ **Note:** moomoo JP does NOT support OpenAPI. You need a Futu HK or moomoo US account.

#### Prerequisites
- Install and launch Moomoo OpenD locally, then sign in with an account that has paper trading access.
- Ensure the OpenD bridge is reachable from the backend (default: `127.0.0.1:11111`).

#### Environment Variables
```bash
BROKER=moomoo
BROKER_ENV=SIMULATE   # set to REAL for live trading
MARKET=US             # or JP / HK
MOOMOO_OPEND_HOST=127.0.0.1
MOOMOO_OPEND_PORT=11111
MOOMOO_ACC_ID=<optional account id>
```

#### Docker Usage

OpenD can be started via `docker compose --profile moomoo up` from the repository root or from `backend/`.
Configure the login-related variables in `backend/.env`:

```bash
MOOMOO_LOGIN_ACCOUNT=your_account
MOOMOO_LOGIN_PASSWORD_MD5=your_password_md5
MOOMOO_LOGIN_REGION=us
MOOMOO_LANG=en
MOOMOO_LOG_LEVEL=info
MOOMOO_API_IP=0.0.0.0
MOOMOO_API_PORT=11111
```

The `opend` service is behind the `moomoo` profile. It will NOT start unless explicitly requested:
```bash
docker compose --profile moomoo up -d
```

#### Connection Test
```bash
cd backend
./scripts/run_moomoo_connection_test.sh
```

#### MD5 (OpenD login password)
```bash
./scripts/generate_md5.sh "your_password"
```

---

### Paper Broker

`BROKER=paper` uses the local SQLModel-backed implementation for simple end-to-end testing.
It does not require OpenD and is the safest default while wiring up the rest of the system.

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
