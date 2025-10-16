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

# Uvicorn 実行（SIGINT/SIGTERM を渡すため exec）
exec uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
