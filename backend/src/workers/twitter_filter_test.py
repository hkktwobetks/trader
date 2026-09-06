"""
Dry-run: fetch last N hours of tweets and show which would be forwarded.
Usage (inside backend container or with env vars set):
    python workers/twitter_filter_test.py [hours=5]
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import httpx

# Reuse existing helpers
from workers.twitter_poll import (
    USERS,
    _build_client,
    _extract_tweet_result,
    _parse_tweets,
    resolve_user_id,
    should_forward_tweet,
    _alert_threads,
    _is_alert_reply,
    TWEET_FEATURES,
    BASE,
    EP_USER_TWEETS_AND_REPLIES,
    EP_USER_TWEETS,
)

HOURS = float(sys.argv[1]) if len(sys.argv) > 1 else 5.0
CUTOFF = datetime.now(timezone.utc) - timedelta(hours=HOURS)


def _parse_created_at(s: str) -> datetime | None:
    """Parse Twitter's 'Mon Jan 01 00:00:00 +0000 2024' format."""
    try:
        return datetime.strptime(s, "%a %b %d %H:%M:%S %z %Y")
    except Exception:
        return None


def _extract_with_time(tr: dict) -> dict | None:
    if tr.get("__typename") == "TweetWithVisibilityResults":
        tr = tr.get("tweet", tr)
    legacy = tr.get("legacy", {})
    base = _extract_tweet_result(tr)
    if base is None:
        return None
    base["created_at"] = _parse_created_at(legacy.get("created_at", ""))
    return base


def _parse_tweets_with_time(data: dict, seen: set) -> list[dict]:
    """Like _parse_tweets but also extracts created_at."""
    user_result = data.get("data", {}).get("user", {}).get("result", {})
    timeline_root = user_result.get("timeline_v2") or user_result.get("timeline") or {}
    instructions = timeline_root.get("timeline", {}).get("instructions", [])

    tweets = []
    for instr in instructions:
        for entry in instr.get("entries", []):
            content = entry.get("content", {})
            item_content = content.get("itemContent", {})
            if item_content:
                tr = item_content.get("tweet_results", {}).get("result")
                if tr:
                    tw = _extract_with_time(tr)
                    if tw and tw["id"] not in seen:
                        seen.add(tw["id"])
                        tweets.append(tw)
                continue
            for sub in content.get("items", []):
                tr = sub.get("item", {}).get("itemContent", {}).get("tweet_results", {}).get("result")
                if tr:
                    tw = _extract_with_time(tr)
                    if tw and tw["id"] not in seen:
                        seen.add(tw["id"])
                        tweets.append(tw)
    return tweets


async def fetch_with_time(client: httpx.AsyncClient, user_id: int, seen: set) -> list[dict]:
    variables = json.dumps({
        "userId": str(user_id),
        "count": 40,
        "includePromotedContent": True,
        "withQuickPromoteEligibilityTweetFields": True,
        "withVoice": True,
    })
    try:
        r = await client.get(
            f"{BASE}/{EP_USER_TWEETS_AND_REPLIES}/UserTweetsAndReplies",
            params={"variables": variables, "features": TWEET_FEATURES},
        )
        if r.status_code == 200:
            return _parse_tweets_with_time(r.json(), seen)
    except Exception:
        pass
    try:
        r = await client.get(
            f"{BASE}/{EP_USER_TWEETS}/UserTweets",
            params={"variables": variables, "features": TWEET_FEATURES},
        )
        r.raise_for_status()
        return _parse_tweets_with_time(r.json(), seen)
    except Exception as e:
        print(f"[error] fetch failed: {e}")
        return []


async def main() -> None:
    if not USERS:
        sys.exit("TWITTER_USERS not set")

    print(f"=== Twitter filter dry-run: last {HOURS:.0f}h (cutoff {CUTOFF.strftime('%H:%M %Z')}) ===\n")

    async with _build_client() as client:
        user_ids: dict[str, int] = {}
        for username in USERS:
            uid = await resolve_user_id(client, username)
            if uid:
                user_ids[username] = uid

        if not user_ids:
            sys.exit("Could not resolve any user IDs")

        seen: set[str] = set()
        all_tweets: list[dict] = []

        for username, uid in user_ids.items():
            tweets = await fetch_with_time(client, uid, seen)
            for tw in tweets:
                tw["_account"] = username
            all_tweets.extend(tweets)

    # Sort chronologically
    all_tweets.sort(key=lambda t: t.get("created_at") or datetime.min.replace(tzinfo=timezone.utc))

    # Simulate forwarding pass (same order as worker would see them)
    local_alert_threads: dict[str, datetime] = {}

    def sim_is_alert_reply(tw: dict) -> bool:
        cutoff = datetime.now() - timedelta(hours=24)
        reply_to = tw.get("in_reply_to")
        conv_id  = tw.get("conversation_id")
        return bool(
            (reply_to and reply_to in local_alert_threads)
            or (conv_id and conv_id in local_alert_threads)
        )

    total = skipped_time = forwarded = not_forwarded = 0

    for tw in all_tweets:
        total += 1
        created = tw.get("created_at")
        if created and created < CUTOFF:
            skipped_time += 1
            continue

        text = tw["text"]
        ts = created.strftime("%m/%d %H:%M") if created else "??:??"
        username = tw.get("username") or tw.get("_account", "?")

        is_reply = sim_is_alert_reply(tw)
        forward = should_forward_tweet(text, tw) or is_reply

        # Determine why it would be forwarded
        reasons = []
        from workers.twitter_poll import (
            ALERT_HASHTAG, ALERT_KEYWORD, SWING_HASHTAG, SWING_KEYWORD,
            OPTION_HASHTAG, OPTION_KEYWORD, _CASHTAG_RE,
        )
        if ALERT_HASHTAG in text or ALERT_KEYWORD in text:
            reasons.append("デイトレアラート")
        if SWING_HASHTAG in text or SWING_KEYWORD in text:
            reasons.append("スイングアラート")
        if OPTION_HASHTAG in text or OPTION_KEYWORD in text:
            reasons.append("オプションアラート")
        if _CASHTAG_RE.search(text):
            reasons.append("$cashtag")
        if is_reply:
            reasons.append(f"reply→{tw.get('in_reply_to') or tw.get('conversation_id')}")

        snippet = text.replace("\n", " ")[:90]

        if forward:
            forwarded += 1
            tag = "✅ FORWARD"
            if reasons:
                tag += f" [{', '.join(reasons)}]"
            print(f"{ts} @{username}  {tag}")
            print(f"   {snippet}")
            if tw.get("in_reply_to"):
                print(f"   reply_to={tw['in_reply_to']}")
            # Track as alert thread if it's a primary alert (not a reply)
            if not is_reply:
                local_alert_threads[tw["id"]] = datetime.now()
        else:
            not_forwarded += 1
            print(f"{ts} @{username}  ── skip")
            print(f"   {snippet}")

        print()

    print(f"=== Summary: {total} fetched, {skipped_time} outside window, "
          f"{forwarded} would forward, {not_forwarded} skipped ===")


if __name__ == "__main__":
    asyncio.run(main())
