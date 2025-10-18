## Moomoo OpenD Integration

### Prerequisites
- Install and launch Moomoo OpenD locally, then sign in with an account that has paper trading access.
- Ensure the OpenD bridge is reachable from the backend (default: `127.0.0.1:11111`).

### Dependencies
- Manage Python packages with [uv](https://docs.astral.sh/uv/).
- Add the Moomoo SDK when preparing the environment:
  ```bash
  uv add futu-api
  uv sync
  ```

### Environment Variables
Update `.env` (or the deployment environment) with the following values:
- `BROKER=moomoo`
- `BROKER_ENV=SIMULATE` (set to `REAL` for live trading)
- `MOOMOO_OPEND_HOST=127.0.0.1`
- `MOOMOO_OPEND_PORT=11111`
- `MOOMOO_ACC_ID=<optional account id>` — omit to use the first available account returned by OpenD.

### Smoke Test
After the API backend dependencies are installed and OpenD is running:
```bash
uv run python scripts/smoke_moomoo.py
```
The script connects to OpenD, fetches current positions, submits a `$1.00` limit buy for one share of `AAPL`, and then cancels any open orders.

### Docker Usage
The backend container does not ship with OpenD. When running via Docker, keep OpenD running on the host machine and expose the host/port back into the container (e.g., using host networking or by forwarding the port).
