#!/usr/bin/env bash
# OpenD を Docker で起動したあと、ホストから接続確認する（backend/.env を読む）
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run python scripts/test_moomoo_connection.py
