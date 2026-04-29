#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${BACKEND_DIR}"

if [[ -x ".venv.local/bin/python" ]]; then
  PYTHON_BIN="${BACKEND_DIR}/.venv.local/bin/python"
  UVICORN_BIN="${BACKEND_DIR}/.venv.local/bin/uvicorn"
elif [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN="${BACKEND_DIR}/.venv/bin/python"
  UVICORN_BIN="${BACKEND_DIR}/.venv/bin/uvicorn"
else
  PYTHON_BIN="$(command -v python3)"
  UVICORN_BIN="$(command -v uvicorn)"
fi

if [[ -z "${PYTHON_BIN:-}" || ! -x "${PYTHON_BIN}" ]]; then
  echo "python が見つかりません" >&2
  exit 1
fi

if [[ -z "${UVICORN_BIN:-}" || ! -x "${UVICORN_BIN}" ]]; then
  echo "uvicorn が見つかりません" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d /tmp/trader-e2e.XXXXXX)"
DB_PATH="${TMP_DIR}/trader-e2e.db"
COOKIE_PATH="${TMP_DIR}/twitter-cookies.json"
LOG_PATH="${TMP_DIR}/server.log"

cleanup() {
  if [[ -n "${SERVER_PID:-}" ]]; then
    kill "${SERVER_PID}" 2>/dev/null || true
    wait "${SERVER_PID}" 2>/dev/null || true
  fi
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

export PYTHONPATH="${BACKEND_DIR}/src"
export DATABASE_URL="sqlite:///${DB_PATH}"
export COOKIE_STORE_PATH="${COOKIE_PATH}"
export BROKER="${BROKER:-paper}"
export AUTO_TRADE_ENABLED="${AUTO_TRADE_ENABLED:-true}"
export MIN_CONFIDENCE="${MIN_CONFIDENCE:-0}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-}"
export XDG_CONFIG_HOME="${TMP_DIR}/xdg-config"
export XDG_CACHE_HOME="${TMP_DIR}/xdg-cache"
mkdir -p "${XDG_CONFIG_HOME}" "${XDG_CACHE_HOME}"

lsof -ti:8000 2>/dev/null | xargs -r kill -9 2>/dev/null || true
sleep 1

(cd "${TMP_DIR}" && "${UVICORN_BIN}" api.main:app --host 127.0.0.1 --port 8000) >"${LOG_PATH}" 2>&1 &
SERVER_PID=$!

for _ in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

if ! curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "API の起動に失敗しました" >&2
  cat "${LOG_PATH}" >&2 || true
  exit 1
fi

echo "===================================="
echo "   Trader System E2E Test"
echo "===================================="

# 1. Health
echo ""
echo "--- 1. Health Check ---"
curl -s http://127.0.0.1:8000/health
echo ""

# 2. Cookie status (before)
echo ""
echo "--- 2. Cookie Status (before) ---"
curl -s http://127.0.0.1:8000/settings/twitter-cookies
echo ""

# 3. Set cookies
echo ""
echo "--- 3. Set Twitter Cookies ---"
curl -s -X POST http://127.0.0.1:8000/settings/twitter-cookies \
  -H "Content-Type: application/json" \
  -d "{\"auth_token\":\"e86297890092d1445d738f88a328d12ebcbf0ec6\",\"ct0\":\"89ea1115bb848b91345d99be169ad1973c0035ecb83b002f7260079ee927f98cf288ae7e40d82d528ef55b73232ad7eacaacf86aee6b01ef92e3cfa79127ae00a5c6e4ad2f53fc3eb276fe5aaa1106ee\"}"
echo ""

# 4. Cookie status (after)
echo ""
echo "--- 4. Cookie Status (after) ---"
curl -s http://127.0.0.1:8000/settings/twitter-cookies
echo ""

# 5. Dashboard
echo ""
echo "--- 5. Dashboard ---"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/dashboard)
SIZE=$(curl -s http://127.0.0.1:8000/dashboard | wc -c)
echo "HTTP $STATUS, $SIZE bytes"

# 6. Post a test signal
echo ""
echo "--- 6. POST /signals (AAPL SELL) ---"
curl -s -X POST http://127.0.0.1:8000/signals \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"\$AAPL looks weak, SELL at 250\",\"source\":\"twitter\",\"meta\":{\"username\":\"test_user\",\"url\":\"https://twitter.com/test/123\",\"id\":\"test_e2e_001\"}}"
echo ""

# 7. Post another signal
echo ""
echo "--- 7. POST /signals (TSLA BUY) ---"
curl -s -X POST http://127.0.0.1:8000/signals \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"TSLA breakout BUY now target 300\",\"source\":\"twitter\",\"meta\":{\"username\":\"trader_bot\",\"url\":\"https://twitter.com/test/456\",\"id\":\"test_e2e_002\"}}"
echo ""

# 8. List signals
echo ""
echo "--- 8. GET /signals ---"
curl -s http://127.0.0.1:8000/signals | "${PYTHON_BIN}" -m json.tool 2>/dev/null || curl -s http://127.0.0.1:8000/signals
echo ""

# 9. List orders
echo ""
echo "--- 9. GET /orders ---"
curl -s http://127.0.0.1:8000/orders | "${PYTHON_BIN}" -m json.tool 2>/dev/null || curl -s http://127.0.0.1:8000/orders
echo ""

echo ""
echo "--- 9.5 GET /positions ---"
curl -s http://127.0.0.1:8000/positions | "${PYTHON_BIN}" -m json.tool 2>/dev/null || curl -s http://127.0.0.1:8000/positions
echo ""

# 10. Twitter tweet fetch test
echo ""
echo "--- 10. Twitter Tweet Fetch (snatchan_comm) ---"
(
cd "${TMP_DIR}"
"${PYTHON_BIN}" -c "
import sys, os
sys.path.insert(0, '${BACKEND_DIR}/src')
os.environ['X_AUTH_TOKEN'] = 'e86297890092d1445d738f88a328d12ebcbf0ec6'
os.environ['X_CT0'] = '89ea1115bb848b91345d99be169ad1973c0035ecb83b002f7260079ee927f98cf288ae7e40d82d528ef55b73232ad7eacaacf86aee6b01ef92e3cfa79127ae00a5c6e4ad2f53fc3eb276fe5aaa1106ee'
os.environ['COOKIE_STORE_PATH'] = '${COOKIE_PATH}'
from app.cookie_store import save_cookies
save_cookies(os.environ['X_AUTH_TOKEN'], os.environ['X_CT0'])

from twitter.scraper import Scraper
scraper = Scraper(cookies={'auth_token': os.environ['X_AUTH_TOKEN'], 'ct0': os.environ['X_CT0']})
info = scraper.users(['snatchan_comm'])
uid = None
for item in info:
    result = item['data']['user']['result']
    uid = int(result.get('rest_id', 0))
    print(f'User: {result[\"legacy\"][\"screen_name\"]} (id={uid}, protected={result[\"legacy\"][\"protected\"]})')

raw = scraper.tweets([uid], limit=20)
count = 0
for item in raw:
    user_data = item.get('data', {}).get('user', {})
    result = user_data.get('result')
    if not result:
        continue
    try:
        instructions = result['timeline_v2']['timeline']['instructions']
    except (KeyError, TypeError):
        continue
    for instr in instructions:
        for entry in instr.get('entries', []):
            content = entry.get('content', {})
            try:
                tr = content['itemContent']['tweet_results']['result']
                if tr.get('__typename') == 'TweetWithVisibilityResults':
                    tr = tr.get('tweet', tr)
                leg = tr.get('legacy', {})
                text = leg.get('full_text', '')
                if text:
                    count += 1
                    if count <= 3:
                        print(f'  Tweet[{count}]: {text[:100]}')
            except (KeyError, TypeError):
                pass
print(f'Total tweets fetched: {count}')
" 2>&1 | grep -v 'Failed to save\|it/s\]'
)

echo ""
echo "===================================="
echo "   E2E Test Complete"
echo "===================================="
