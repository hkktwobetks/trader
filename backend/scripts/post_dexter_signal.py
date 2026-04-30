#!/usr/bin/env python3
"""Post a Dexter-generated signal to the backend API.

Examples:
  python scripts/post_dexter_signal.py '$AAPL BUY swing idea from Dexter'
  echo '$TSLA SELL' | python scripts/post_dexter_signal.py --stdin
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local", override=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Post a Dexter signal to the trader backend.")
    parser.add_argument("text", nargs="*", help="Signal text, for example: '$AAPL BUY swing trade'")
    parser.add_argument("--stdin", action="store_true", help="Read signal text from stdin")
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("API_BASE_URL", "http://127.0.0.1:8000"),
        help="Backend API base URL",
    )
    parser.add_argument(
        "--broker-env",
        default=os.getenv("DEXTER_BROKER_ENV", "SIMULATE"),
        choices=["SIMULATE", "REAL"],
        help="Target broker environment for the signal",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.stdin:
        text = sys.stdin.read().strip()
    else:
        text = " ".join(args.text).strip()

    if not text:
        print("Signal text is required.", file=sys.stderr)
        return 2

    payload = {
        "text": text,
        "source": "dexter",
        "meta": {
            "broker_env": args.broker_env,
            "origin": "post_dexter_signal.py",
        },
    }
    response = requests.post(f"{args.api_base_url.rstrip('/')}/signals", json=payload, timeout=10)
    response.raise_for_status()
    print(response.text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
