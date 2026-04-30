#!/usr/bin/env python3
"""Run a Dexter query once and optionally post the result as a simulation signal.

Requires:
  - a local Dexter checkout
  - Bun installed
  - Dexter environment variables configured in the Dexter repo
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local", override=True)
sys.path.insert(0, str(BASE_DIR / "src"))

from app.dexter_bridge import build_dexter_query, get_dexter_dir_from_env, post_dexter_signal, run_dexter_once


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Dexter once and post a signal to the backend.")
    parser.add_argument("query", nargs="+", help="Research query for Dexter")
    parser.add_argument(
        "--dexter-dir",
        default=os.getenv("DEXTER_DIR", ""),
        help="Path to the local Dexter checkout",
    )
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"),
        help="Backend API base URL",
    )
    parser.add_argument(
        "--broker-env",
        default=os.getenv("DEXTER_BROKER_ENV", "SIMULATE"),
        choices=["SIMULATE", "REAL"],
        help="Target broker environment for the posted signal",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print Dexter output without posting it")
    return parser.parse_args()

def main() -> int:
    args = parse_args()
    if args.dexter_dir:
        dexter_dir = Path(args.dexter_dir).expanduser()
    else:
        try:
            dexter_dir = get_dexter_dir_from_env()
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 2

    dexter_query = build_dexter_query(" ".join(args.query).strip())
    answer = run_dexter_once(dexter_dir, dexter_query)
    print(answer)

    if answer.strip() == "NO_SIGNAL" or args.dry_run:
        return 0

    result = post_dexter_signal(
        args.api_base_url,
        answer,
        args.broker_env,
        " ".join(args.query).strip(),
        "run_dexter_signal.py",
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
