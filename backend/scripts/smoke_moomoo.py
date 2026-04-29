"""Moomoo ブローカー経由のスモークテスト（OpenD 起動・BROKER=moomoo が必要）。"""
import logging
import sys
import traceback
from pathlib import Path
from pprint import pprint

from dotenv import load_dotenv

# backend から実行: uv run python scripts/smoke_moomoo.py
_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND / "src"))
load_dotenv(_BACKEND / ".env")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from broker import get_broker

    broker = get_broker()
    if broker.name != "moomoo":
        raise RuntimeError(f"Smoke test requires BROKER=moomoo. Current broker: {broker.name}")

    logging.info("Fetching current positions...")
    try:
        positions = broker.positions()
    except Exception:
        logging.exception("Failed to fetch positions from Moomoo.")
        raise
    else:
        pprint(positions)

    logging.info("Submitting test order for AAPL (limit $1)...")
    try:
        order = broker.place_order("AAPL", "BUY", 1, price=1.0, order_type="LIMIT", tif="DAY")
    except Exception:
        logging.exception("Failed to place smoke-test order with Moomoo.")
        raise
    else:
        pprint(order)

    logging.info("Cancelling all open orders...")
    try:
        broker.cancel_all()
    except Exception:
        logging.exception("Failed to cancel open orders on Moomoo.")
        raise
    logging.info("Smoke test complete.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI convenience
        traceback.print_exc()
        sys.exit(str(exc))
