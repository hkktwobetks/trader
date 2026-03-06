#!/usr/bin/env bash
set -Eeuo pipefail

# 安全に .env を読み込む（スペース/記号でもOK）
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

# デフォルト値（.env が無い/未設定でも動くように）
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"

# ポートがすでに使用中なら 0（true）を返す
is_port_in_use() {
  local port="$1"

  # macOS / Linux: lsof があればそれを使う
  if command -v lsof >/dev/null 2>&1; then
    # lsof は「見つかったら 0」なので、そのままだと「使用中=true」になる
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
    return $?
  fi

  # フォールバック（lsof 無い場合）: bash の /dev/tcp
  # 接続できたら「何かが待ち受けている」ので使用中=true
  if (echo >/dev/tcp/127.0.0.1/"${port}") >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

if is_port_in_use "${API_PORT}"; then
  echo "Port ${API_PORT} is already in use. Searching for a free port..." >&2
  for p in $(seq 8001 8100); do
    if ! is_port_in_use "$p"; then
      API_PORT="$p"
      echo "Using port ${API_PORT}." >&2
      break
    fi
  done
fi

# モジュール検索パス（app / api を src から解決）
export PYTHONPATH="${PYTHONPATH:-}:./src"

# Uvicorn 実行（uv があれば uv run、なければ python3 -m）
if command -v uv >/dev/null 2>&1; then
  exec uv run uvicorn api.main:app --reload --host "${API_HOST}" --port "${API_PORT}"
else
  exec python3 -m uvicorn api.main:app --reload --host "${API_HOST}" --port "${API_PORT}"
fi
