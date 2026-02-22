import os
import time
import logging
from typing import Iterable, Dict, Any, List, Set

import requests
from twitter.scraper import Scraper  # pip: twitter-api-client

from app.utils import naive_extract
from app.cookie_store import load_cookies, get_version, save_cookies
from workers.twitter_auth_helper import get_twitter_cookies, refresh_cookies, validate_cookies

logging.basicConfig(level=logging.INFO, format='[twitter_worker] %(message)s')
log = logging.getLogger(__name__)

# cookie_store 経由で読み込み（API / ファイル / 環境変数）
X_AUTH_TOKEN, X_CT0 = load_cookies()
if not X_AUTH_TOKEN or not X_CT0:
    # フォールバック: twitter_auth_helper
    X_AUTH_TOKEN, X_CT0 = get_twitter_cookies(auto_refresh=True)
    if X_AUTH_TOKEN and X_CT0:
        save_cookies(X_AUTH_TOKEN, X_CT0)

POLL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "30"))
API_BASE = os.getenv("API_BASE_URL", "http://api:8000")

USERS = [u.strip() for u in os.getenv("TWITTER_USERS", "").split(",") if u.strip()]
QUERY = os.getenv("TWITTER_QUERY", "").strip()

scraper: Scraper | None = None
if X_AUTH_TOKEN and X_CT0:
    scraper = Scraper(cookies={"auth_token": X_AUTH_TOKEN, "ct0": X_CT0})
else:
    log.warning("Cookie 未設定。ダッシュボード /dashboard から設定してください")


def resolve_user_ids(usernames: List[str]) -> Dict[str, int]:
    if not usernames:
        return {}
    info = scraper.users(usernames)
    mapping: Dict[str, int] = {}
    for item in info:
        try:
            result = item["data"]["user"]["result"]
            legacy = result.get("legacy", {})
            screen_name = legacy.get("screen_name", "")
            user_id = int(result.get("rest_id", legacy.get("id_str", 0)))
            if screen_name and user_id:
                mapping[screen_name] = user_id
        except (KeyError, TypeError, ValueError) as e:
            log.warning(f"Failed to parse user info: {e}")
    log.info(f"resolved users: {mapping}")
    return mapping


def _parse_tweet_result(tweet_result: Dict) -> Iterable[Dict[str, Any]]:
    if not tweet_result:
        return
    if tweet_result.get("__typename") == "TweetWithVisibilityResults":
        tweet_result = tweet_result.get("tweet", tweet_result)
    legacy = tweet_result.get("legacy", {})
    full_text = legacy.get("full_text", "")
    if not full_text:
        return
    rest_id = tweet_result.get("rest_id", "")
    core = tweet_result.get("core", {})
    user_legacy = core.get("user_results", {}).get("result", {}).get("legacy", {})
    yield {
        "id": rest_id,
        "text": full_text,
        "user_id": int(legacy.get("user_id_str", 0)),
        "username": user_legacy.get("screen_name", legacy.get("screen_name", "")),
        "created_at": legacy.get("created_at"),
        "url": f"https://twitter.com/i/web/status/{rest_id}",
    }


def _extract_tweets_from_timeline(raw: List[Dict]) -> Iterable[Dict[str, Any]]:
    for item in raw:
        instructions = []
        try:
            instructions = item["data"]["user"]["result"]["timeline_v2"]["timeline"]["instructions"]
        except (KeyError, TypeError):
            pass
        if not instructions:
            try:
                instructions = item["data"]["search_by_raw_query"]["search_timeline"]["timeline"]["instructions"]
            except (KeyError, TypeError):
                pass
        if not instructions:
            legacy = item.get("legacy") or item.get("result", {}).get("legacy", {})
            if legacy and legacy.get("full_text"):
                rest_id = item.get("rest_id") or item.get("result", {}).get("rest_id", "")
                yield {
                    "id": rest_id,
                    "text": legacy.get("full_text", ""),
                    "user_id": int(legacy.get("user_id_str", 0)),
                    "username": legacy.get("screen_name", ""),
                    "created_at": legacy.get("created_at"),
                    "url": f"https://twitter.com/i/web/status/{rest_id}",
                }
            continue

        for instr in instructions:
            entries = instr.get("entries") or []
            for entry in entries:
                content = entry.get("content", {})
                tweet_result = None
                try:
                    tweet_result = content["itemContent"]["tweet_results"]["result"]
                except (KeyError, TypeError):
                    pass
                if tweet_result is not None:
                    yield from _parse_tweet_result(tweet_result)
                    continue
                for sub_item in content.get("items", []):
                    try:
                        tweet_result = sub_item["item"]["itemContent"]["tweet_results"]["result"]
                    except (KeyError, TypeError):
                        continue
                    yield from _parse_tweet_result(tweet_result)


def fetch_user_tweets(user_ids: Iterable[int]) -> Iterable[Dict[str, Any]]:
    raw = scraper.tweets(list(user_ids))
    yield from _extract_tweets_from_timeline(raw)


def fetch_search(query: str) -> Iterable[Dict[str, Any]]:
    raw = scraper.search(query)
    yield from _extract_tweets_from_timeline(raw)


def post_signal(text: str, meta: Dict[str, Any]) -> None:
    try:
        r = requests.post(
            f"{API_BASE}/signals",
            json={"text": text, "source": "twitter", "meta": meta},
            timeout=5,
        )
        r.raise_for_status()
        log.info(f"-> posted to API: {meta.get('url')}")
    except Exception as e:
        log.warning(f"API post failed: {e}")


def _reload_scraper_if_needed() -> bool:
    """cookie_store に新しい Cookie があれば scraper を再初期化"""
    global scraper, X_AUTH_TOKEN, X_CT0
    new_auth, new_ct0 = load_cookies()
    if not new_auth or not new_ct0:
        return False
    if new_auth == X_AUTH_TOKEN and new_ct0 == X_CT0 and scraper is not None:
        return False  # 変更なし
    X_AUTH_TOKEN, X_CT0 = new_auth, new_ct0
    scraper = Scraper(cookies={"auth_token": X_AUTH_TOKEN, "ct0": X_CT0})
    log.info(f"Scraper を再初期化しました (version={get_version()})")
    return True


def main() -> None:
    global scraper, X_AUTH_TOKEN, X_CT0

    if not USERS and not QUERY:
        raise SystemExit("TWITTER_USERS or TWITTER_QUERY must be set in .env")

    seen: Set[str] = set()
    user_ids: Dict[str, int] = {}
    consecutive_errors = 0
    max_errors_before_refresh = 3

    while True:
        # ダッシュボードから Cookie が更新されたかチェック
        if _reload_scraper_if_needed():
            user_ids = resolve_user_ids(USERS) if USERS else {}
            consecutive_errors = 0

        if scraper is None:
            log.info("Cookie 未設定。ダッシュボード /dashboard から設定してください。%ds 後にリトライ...", POLL_SEC)
            time.sleep(POLL_SEC)
            continue

        if not user_ids and USERS:
            user_ids = resolve_user_ids(USERS)

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
                parsed = naive_extract(text)
                log.info(f"[tweet] {tw['username']}: {text}")
                if parsed:
                    log.info(f"  parsed: {parsed}")
                    post_signal(text, tw)

            consecutive_errors = 0

        except Exception as e:
            log.warning(f"loop error: {e}")
            consecutive_errors += 1

            if consecutive_errors >= max_errors_before_refresh:
                log.info("エラーが続いています。Cookie を再チェック...")
                if _reload_scraper_if_needed():
                    user_ids = resolve_user_ids(USERS) if USERS else {}
                    consecutive_errors = 0
                elif refresh_cookies():
                    X_AUTH_TOKEN, X_CT0 = get_twitter_cookies(auto_refresh=False)
                    if X_AUTH_TOKEN and X_CT0:
                        save_cookies(X_AUTH_TOKEN, X_CT0)
                        scraper = Scraper(cookies={"auth_token": X_AUTH_TOKEN, "ct0": X_CT0})
                        user_ids = resolve_user_ids(USERS) if USERS else {}
                        consecutive_errors = 0
                        log.info("Cookie を更新しました")
                    else:
                        log.error("Cookie の更新に失敗")

        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
