import logging
import sys
import traceback
from pprint import pprint

from dotenv import load_dotenv


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    load_dotenv()

    from broker import get_broker

    broker = get_broker()
    if broker.name != "moomoo":
        raise RuntimeError(f"Smoke test requires BROKER=moomoo. Current broker: {broker.name}")

    logging.info("Fetching current positions...")
    try:
        positions = broker.positions()
    except Exception:  # pragma: no cover - script level error handling
        logging.exception("Failed to fetch positions from Moomoo.")
        raise
    else:
        pprint(positions)

    logging.info("Submitting test order for AAPL...")
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
