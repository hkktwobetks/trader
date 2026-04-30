from __future__ import annotations

import logging
import os
import time

from app.dexter_bridge import build_dexter_query, get_dexter_dir_from_env, post_dexter_signal, run_dexter_once

logging.basicConfig(level=logging.INFO, format="[dexter_worker] %(message)s")
log = logging.getLogger(__name__)

POLL_SEC = int(os.getenv("DEXTER_POLL_INTERVAL_SEC", "1800"))
QUERY = os.getenv("DEXTER_QUERY", "").strip()
API_BASE = os.getenv("API_BASE_URL", "http://api:8000")
BROKER_ENV = os.getenv("DEXTER_BROKER_ENV", "SIMULATE").upper()


def main() -> None:
    if not QUERY:
        log.info("DEXTER_QUERY not set — worker idle. Set DEXTER_QUERY in .env to enable.")
        while True:
            time.sleep(3600)

    while True:
        try:
            dexter_dir = get_dexter_dir_from_env()
            answer = run_dexter_once(dexter_dir, build_dexter_query(QUERY))
            log.info("Dexter answer:\n%s", answer)
            if answer.strip() != "NO_SIGNAL":
                result = post_dexter_signal(API_BASE, answer, BROKER_ENV, QUERY, "workers.dexter_poll")
                log.info("Posted Dexter signal: %s", result)
            else:
                log.info("Dexter returned NO_SIGNAL")
        except Exception as exc:
            log.warning("Dexter loop failed: %s", exc)

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
