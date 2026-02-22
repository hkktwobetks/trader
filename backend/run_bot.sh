#!/usr/bin/env bash
set -Eeuo pipefail

# 安全に .env を読み込む（スペース/記号でもOK）
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

# モジュール検索パス
export PYTHONPATH="${PYTHONPATH:-./src}:./src"

# Bot プロセス起動
exec uv run python -m workers.scheduler
