#!/usr/bin/env bash
set -Eeuo pipefail

# 安全に .env を読み込む（スペース/記号でもOK）
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

# モジュール検索パス（app / api を src から解決）
export PYTHONPATH="${PYTHONPATH:-}:./src"

# Uvicorn 実行（uv があれば uv run、なければ python3 -m）
if command -v uv >/dev/null 2>&1; then
  exec uv run uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
else
  exec python3 -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
fi
