#!/bin/bash
cd /home/daiki/trader/backend
source /tmp/trader-venv/bin/activate
export PYTHONPATH=src
# Kill any existing server
lsof -ti:8000 2>/dev/null | xargs -r kill -9 2>/dev/null
sleep 1
# Start server
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!
sleep 3

echo "===================================="
echo "   Trader System E2E Test"
echo "===================================="

# 1. Health
echo ""
echo "--- 1. Health Check ---"
curl -s http://localhost:8000/health
echo ""

# 2. Cookie status (before)
echo ""
echo "--- 2. Cookie Status (before) ---"
curl -s http://localhost:8000/settings/twitter-cookies
echo ""

# 3. Set cookies
echo ""
echo "--- 3. Set Twitter Cookies ---"
curl -s -X POST http://localhost:8000/settings/twitter-cookies \
  -H "Content-Type: application/json" \
  -d "{\"auth_token\":\"e86297890092d1445d738f88a328d12ebcbf0ec6\",\"ct0\":\"89ea1115bb848b91345d99be169ad1973c0035ecb83b002f7260079ee927f98cf288ae7e40d82d528ef55b73232ad7eacaacf86aee6b01ef92e3cfa79127ae00a5c6e4ad2f53fc3eb276fe5aaa1106ee\"}"
echo ""

# 4. Cookie status (after)
echo ""
echo "--- 4. Cookie Status (after) ---"
curl -s http://localhost:8000/settings/twitter-cookies
echo ""

# 5. Dashboard
echo ""
echo "--- 5. Dashboard ---"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/dashboard)
SIZE=$(curl -s http://localhost:8000/dashboard | wc -c)
echo "HTTP $STATUS, $SIZE bytes"

# 6. Post a test signal
echo ""
echo "--- 6. POST /signals (AAPL SELL) ---"
curl -s -X POST http://localhost:8000/signals \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"\$AAPL looks weak, SELL at 250\",\"source\":\"twitter\",\"meta\":{\"username\":\"test_user\",\"url\":\"https://twitter.com/test/123\",\"id\":\"test_e2e_001\"}}"
echo ""

# 7. Post another signal
echo ""
echo "--- 7. POST /signals (TSLA BUY) ---"
curl -s -X POST http://localhost:8000/signals \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"TSLA breakout BUY now target 300\",\"source\":\"twitter\",\"meta\":{\"username\":\"trader_bot\",\"url\":\"https://twitter.com/test/456\",\"id\":\"test_e2e_002\"}}"
echo ""

# 8. List signals
echo ""
echo "--- 8. GET /signals ---"
curl -s http://localhost:8000/signals | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/signals
echo ""

# 9. List orders
echo ""
echo "--- 9. GET /orders ---"
curl -s http://localhost:8000/orders | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/orders
echo ""

# 10. Twitter tweet fetch test
echo ""
echo "--- 10. Twitter Tweet Fetch (snatchan_comm) ---"
python3 -c "
import sys, os
sys.path.insert(0, 'src')
os.environ['X_AUTH_TOKEN'] = 'e86297890092d1445d738f88a328d12ebcbf0ec6'
os.environ['X_CT0'] = '89ea1115bb848b91345d99be169ad1973c0035ecb83b002f7260079ee927f98cf288ae7e40d82d528ef55b73232ad7eacaacf86aee6b01ef92e3cfa79127ae00a5c6e4ad2f53fc3eb276fe5aaa1106ee'
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

echo ""
echo "===================================="
echo "   E2E Test Complete"
echo "===================================="

# Cleanup
kill $SERVER_PID 2>/dev/null
