import os
import time
import logging
from typing import Iterable, Dict, Any, List, Set

import requests
from twitter.scraper import Scraper  # pip: twitter-api-client

from app.utils import naive_extract  # 既存の簡易パーサを再利用

logging.basicConfig(level=logging.INFO, format='[twitter_worker] %(message)s')
log = logging.getLogger(__name__)

X_AUTH_TOKEN = os.getenv("X_AUTH_TOKEN", "")
X_CT0 = os.getenv("X_CT0", "")
POLL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "30"))
API_BASE = os.getenv("API_BASE_URL", "http://api:8000")

USERS = [u.strip() for u in os.getenv("TWITTER_USERS", "").split(",") if u.strip()]
QUERY = os.getenv("TWITTER_QUERY", "").strip()

if not X_AUTH_TOKEN or not X_CT0:
    raise SystemExit("X_AUTH_TOKEN / X_CT0 が未設定です（.env を更新して再起動してください）")

scraper = Scraper(cookies={"auth_token": X_AUTH_TOKEN, "ct0": X_CT0})

def resolve_user_ids(usernames: List[str]) -> Dict[str, int]:
    if not usernames:
        return {}
    info = scraper.users(usernames)  # [{id, screen_name, ...}, ...]
    mapping = {u.screen_name: int(u.id) for u in info}
    log.info(f"resolved users: {mapping}")
    return mapping

def fetch_user_tweets(user_ids: Iterable[int]) -> Iterable[Dict[str, Any]]:
    # tweets([id, ...]) は各ユーザーの新しい順タイムライン
    for t in scraper.tweets(list(user_ids)):
        # t は “基本的に” JSON 互換のオブジェクト（.get で取り出し可能）
        legacy = t.get("legacy") or {}
        full_text = legacy.get("full_text") or ""
        yield {
            "id": t.get("rest_id") or t.get("id"),
            "text": full_text,
            "user_id": int(t.get("user_id_str") or legacy.get("user_id_str") or 0),
            "username": legacy.get("screen_name") or "",
            "created_at": legacy.get("created_at"),
            "url": f'https://twitter.com/i/web/status/{t.get("rest_id") or t.get("id")}',
        }

def fetch_search(query: str) -> Iterable[Dict[str, Any]]:
    # 検索ストリーム（内部APIラップ）。鍵垢は“あなたに見える範囲”のみヒット
    for t in scraper.search(query):
        legacy = t.get("legacy") or {}
        full_text = legacy.get("full_text") or ""
        yield {
            "id": t.get("rest_id") or t.get("id"),
            "text": full_text,
            "user_id": int(t.get("user_id_str") or legacy.get("user_id_str") or 0),
            "username": legacy.get("screen_name") or "",
            "created_at": legacy.get("created_at"),
            "url": f'https://twitter.com/i/web/status/{t.get("rest_id") or t.get("id")}',
        }

def post_signal(text: str, meta: Dict[str, Any]) -> None:
    """
    あなたのAPIに流す。FastAPI 側で /signals を受けている想定。
    適宜エンドポイント名を合わせてください。
    """
    try:
        r = requests.post(
            f"{API_BASE}/signals",
            json={"text": text, "source": "twitter", "meta": meta},
            timeout=5,
        )
        r.raise_for_status()
        log.info(f"→ posted to API: {meta.get('url')}")
    except Exception as e:
        log.warning(f"API post failed: {e}")

def main() -> None:
    if not USERS and not QUERY:
        raise SystemExit("TWITTER_USERS か TWITTER_QUERY のどちらかを .env に設定してください")

    seen: Set[str] = set()
    user_ids: Dict[str, int] = resolve_user_ids(USERS) if USERS else {}

    while True:
        try:
            items: Iterable[Dict[str, Any]]
            if user_ids:
                items = fetch_user_tweets(user_ids.values())
            else:
                items = fetch_search(QUERY)

            for tw in items:
                tid = str(tw["id"])
                if tid in seen:
                    continue
                seen.add(tid)

                text = tw["text"]
                parsed = naive_extract(text)  # 例: "$ALM 7.71でイン ..." → 売買/水準/TP/SL を抽出
                log.info(f"[tweet] {tw['username']}: {text}")
                if parsed:
                    log.info(f"  parsed: {parsed}")
                    post_signal(text, tw)

        except Exception as e:
            log.warning(f"loop error: {e}")

        time.sleep(POLL_SEC)

if __name__ == "__main__":
    main()
