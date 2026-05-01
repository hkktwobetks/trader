"""Twitter polling worker — direct GraphQL httpx client."""
import asyncio
import json
import logging
import os

import httpx

from app.cookie_store import load_cookies
from app.utils import naive_extract

logging.basicConfig(level=logging.INFO, format="[twitter_worker] %(message)s")
log = logging.getLogger(__name__)

POLL_SEC = int(os.getenv("POLL_INTERVAL_SEC", "30"))
API_BASE = os.getenv("API_BASE_URL", "http://api:8000")
POST_TIMEOUT_SEC = int(os.getenv("TWITTER_POST_TIMEOUT_SEC", "120"))
USERS = [u.strip() for u in os.getenv("TWITTER_USERS", "").split(",") if u.strip()]
QUERY = os.getenv("TWITTER_QUERY", "").strip()

ALERT_HASHTAG = "#デイトレアラート"
ALERT_KEYWORD = "デイトレアラート"
SWING_HASHTAG = "#スイングアラート"
SWING_KEYWORD = "スイングアラート"

# エンドポイント ID は Twitter のデプロイで変わることがある → env で上書き可能
EP_USER_TWEETS = os.getenv("TW_EP_USER_TWEETS", "naBcZ4al-iTCFBYGOAMzBQ")
EP_USER_BY_SCREENNAME = os.getenv("TW_EP_USER_BY_SCREENNAME", "sLVLhk0bGj3MVFEKTdax1w")

BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs="
    "1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)
BASE = "https://x.com/i/api/graphql"

TWEET_FEATURES = json.dumps({
    "rweb_video_screen_enabled": False,
    "rweb_cashtags_enabled": True,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "verified_phone_label_enabled": False,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
})


def _load_worker_cookies() -> tuple[str, str]:
    auth_token, ct0 = load_cookies()
    if auth_token and ct0:
        return auth_token, ct0
    return os.getenv("X_AUTH_TOKEN", ""), os.getenv("X_CT0", "")


def _build_client() -> httpx.AsyncClient:
    auth_token, ct0 = _load_worker_cookies()
    return httpx.AsyncClient(
        cookies={"auth_token": auth_token, "ct0": ct0},
        headers={
            "authorization": f"Bearer {BEARER}",
            "x-csrf-token": ct0,
            "x-twitter-active-user": "yes",
            "x-twitter-auth-type": "OAuth2Session",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        },
        follow_redirects=True,
        timeout=15,
    )


async def resolve_user_id(client: httpx.AsyncClient, username: str) -> int | None:
    variables = json.dumps({
        "screen_name": username,
        "withSafetyModeUserFields": True,
    })
    features = json.dumps({
        "hidden_profile_likes_enabled": True,
        "hidden_profile_subscriptions_enabled": True,
        "responsive_web_graphql_exclude_directive_enabled": True,
        "verified_phone_label_enabled": False,
        "creator_subscriptions_tweet_preview_api_enabled": True,
        "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
        "responsive_web_graphql_timeline_navigation_enabled": True,
    })
    try:
        r = await client.get(
            f"{BASE}/{EP_USER_BY_SCREENNAME}/UserByScreenName",
            params={"variables": variables, "features": features},
        )
        r.raise_for_status()
        result = r.json()["data"]["user"]["result"]
        uid = int(result["rest_id"])
        log.info("resolved: @%s -> %d (protected=%s)", username, uid, result.get("legacy", {}).get("protected"))
        return uid
    except Exception as e:
        log.warning("user resolve failed for @%s: %s", username, e)
        return None


def _extract_tweet_result(tr: dict) -> dict | None:
    if tr.get("__typename") == "TweetWithVisibilityResults":
        tr = tr.get("tweet", tr)
    legacy = tr.get("legacy", {})
    tid = tr.get("rest_id", "")
    text = legacy.get("full_text", "")
    if not tid or not text:
        return None
    user_result = tr.get("core", {}).get("user_results", {}).get("result", {})
    # screen_name moved to core in newer Twitter API responses
    username = (
        user_result.get("core", {}).get("screen_name")
        or user_result.get("legacy", {}).get("screen_name", "")
    )
    return {"id": tid, "text": text, "username": username, "url": f"https://twitter.com/i/web/status/{tid}"}


def _parse_tweets(data: dict, seen: set) -> list[dict]:
    user_result = data.get("data", {}).get("user", {}).get("result", {})
    timeline_root = user_result.get("timeline_v2") or user_result.get("timeline") or {}
    instructions = timeline_root.get("timeline", {}).get("instructions", [])

    tweets = []
    for instr in instructions:
        for entry in instr.get("entries", []):
            content = entry.get("content", {})
            # TimelineTimelineItem — single tweet
            item_content = content.get("itemContent", {})
            if item_content:
                tr = item_content.get("tweet_results", {}).get("result")
                if tr:
                    tw = _extract_tweet_result(tr)
                    if tw and tw["id"] not in seen:
                        seen.add(tw["id"])
                        tweets.append(tw)
                continue
            # TimelineTimelineModule — list of items (e.g. pinned tweets)
            for sub in content.get("items", []):
                tr = sub.get("item", {}).get("itemContent", {}).get("tweet_results", {}).get("result")
                if tr:
                    tw = _extract_tweet_result(tr)
                    if tw and tw["id"] not in seen:
                        seen.add(tw["id"])
                        tweets.append(tw)
    return tweets


async def fetch_user_tweets(client: httpx.AsyncClient, user_id: int, seen: set) -> list[dict]:
    variables = json.dumps({
        "userId": str(user_id),
        "count": 20,
        "includePromotedContent": True,
        "withQuickPromoteEligibilityTweetFields": True,
        "withVoice": True,
    })
    try:
        r = await client.get(
            f"{BASE}/{EP_USER_TWEETS}/UserTweets",
            params={"variables": variables, "features": TWEET_FEATURES},
        )
        r.raise_for_status()
        return _parse_tweets(r.json(), seen)
    except Exception as e:
        log.warning("tweet fetch failed user_id=%d: %s", user_id, e)
        return []


def post_signal(text: str, meta: dict) -> None:
    try:
        r = httpx.post(
            f"{API_BASE}/signals",
            json={"text": text, "source": "twitter", "meta": meta},
            timeout=POST_TIMEOUT_SEC,
        )
        r.raise_for_status()
        log.info("-> posted: %s", meta.get("url"))
    except Exception as e:
        log.warning("API post failed: %s", e)


def heartbeat() -> bool:
    """Notify backend we are alive. Returns True if polling is enabled."""
    try:
        r = httpx.post(f"{API_BASE}/workers/twitter/heartbeat", timeout=5)
        if r.status_code == 200:
            return bool(r.json().get("enabled", True))
    except Exception as e:
        log.debug("heartbeat failed: %s", e)
    return True  # default to enabled when backend is unreachable


def should_forward_tweet(text: str) -> bool:
    return (
        "$" in text
        or ALERT_HASHTAG in text
        or ALERT_KEYWORD in text
        or SWING_HASHTAG in text
        or SWING_KEYWORD in text
    )


async def main() -> None:
    if not USERS and not QUERY:
        raise SystemExit("TWITTER_USERS or TWITTER_QUERY must be set in .env")
    auth_token, ct0 = _load_worker_cookies()
    if not auth_token or not ct0:
        raise SystemExit("X_AUTH_TOKEN and X_CT0 must be set")

    async with _build_client() as client:
        user_ids: dict[str, int] = {}
        for username in USERS:
            uid = await resolve_user_id(client, username)
            if uid:
                user_ids[username] = uid

        if USERS and not user_ids:
            raise SystemExit("Could not resolve any Twitter user IDs")

        seen: set[str] = set()
        log.info("poll loop started: users=%s interval=%ds", list(user_ids.keys()), POLL_SEC)

        while True:
            enabled = heartbeat()
            if enabled:
                for username, uid in user_ids.items():
                    for tw in await fetch_user_tweets(client, uid, seen):
                        text = tw["text"]
                        log.info("[tweet] @%s: %s", tw.get("username", username), text[:80])
                        if should_forward_tweet(text):
                            if "$" in text:
                                reason = "$ticker"
                            elif SWING_HASHTAG in text or SWING_KEYWORD in text:
                                reason = SWING_KEYWORD
                            else:
                                reason = ALERT_KEYWORD
                            log.info("  -> forwarding to API (%s)", reason)
                            post_signal(text, tw)
            else:
                log.info("polling paused (disabled via API settings)")
            await asyncio.sleep(POLL_SEC)


if __name__ == "__main__":
    asyncio.run(main())
