"""
指定ユーザーの最新ツイートを取得し、LLMで解析するスクリプト
"""
import os
import json
import re
from pathlib import Path
from dotenv import load_dotenv
import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

FEATURES = {
    "rweb_tipjar_consumption_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "articles_preview_enabled": True,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_enhance_cards_enabled": False,
    "responsive_web_media_download_video_enabled": False,
    "hidden_profile_likes_enabled": True,
    "hidden_profile_subscriptions_enabled": True,
    "subscriptions_verification_info_is_identity_verified_enabled": True,
    "subscriptions_verification_info_verified_since_enabled": True,
    "highlights_tweets_tab_ui_enabled": True,
    "responsive_web_twitter_article_notes_tab_enabled": True,
    "subscriptions_feature_can_gift_premium": True,
}

def get_headers():
    auth_token = os.getenv("X_AUTH_TOKEN")
    ct0 = os.getenv("X_CT0")
    return {
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "cookie": f"auth_token={auth_token}; ct0={ct0}",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "ja",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "accept": "*/*",
    }

def fetch_latest_tweet(username: str) -> dict | None:
    auth_token = os.getenv("X_AUTH_TOKEN")
    ct0 = os.getenv("X_CT0")
    
    if not auth_token or not ct0 or auth_token == "xxxxx":
        print("❌ Cookieが設定されていません")
        return None
    
    headers = get_headers()
    
    with httpx.Client(follow_redirects=True, timeout=30) as client:
        print(f"ユーザー @{username} の情報を取得中...")
        
        user_gql_url = "https://twitter.com/i/api/graphql/NimuplG1OB7Fd2btCLdBOw/UserByScreenName"
        
        variables = {"screen_name": username, "withSafetyModeUserFields": True}
        
        params = {
            "variables": json.dumps(variables, separators=(',', ':')),
            "features": json.dumps(FEATURES, separators=(',', ':')),
            "fieldToggles": json.dumps({"withAuxiliaryUserLabels": False}, separators=(',', ':')),
        }
        
        resp = client.get(user_gql_url, headers=headers, params=params)
        
        if resp.status_code != 200:
            print(f"❌ ユーザー取得失敗: {resp.status_code}")
            print(f"Response: {resp.text[:500]}")
            return None
        
        try:
            user_data = resp.json()
            user_id = user_data["data"]["user"]["result"]["rest_id"]
            print(f"ユーザーID: {user_id}")
        except Exception as e:
            print(f"❌ ユーザーID抽出失敗: {e}")
            print(f"Response: {resp.text[:500]}")
            return None
        
        print("最新ツイートを取得中...")
        timeline_url = "https://twitter.com/i/api/graphql/V1ze5q3ijDS1VeLwLY0m7g/UserTweets"
        
        variables = {
            "userId": user_id,
            "count": 20,
            "includePromotedContent": True,
            "withQuickPromoteEligibilityTweetFields": True,
            "withVoice": True,
            "withV2Timeline": True,
        }
        
        params = {
            "variables": json.dumps(variables, separators=(',', ':')),
            "features": json.dumps(FEATURES, separators=(',', ':')),
        }
        
        resp = client.get(timeline_url, headers=headers, params=params)
        
        if resp.status_code != 200:
            print(f"❌ ツイート取得失敗: {resp.status_code}")
            print(f"Response: {resp.text[:500]}")
            return None
        
        return resp.json()

def extract_tweets(data: dict) -> list[dict]:
    tweets = []
    try:
        instructions = data["data"]["user"]["result"]["timeline_v2"]["timeline"]["instructions"]
        for inst in instructions:
            for entry in inst.get("entries", []):
                content = entry.get("content", {})
                item_content = content.get("itemContent", {})
                result = item_content.get("tweet_results", {}).get("result", {})
                
                if result.get("__typename") == "Tweet":
                    legacy = result.get("legacy", {})
                elif result.get("__typename") == "TweetWithVisibilityResults":
                    legacy = result.get("tweet", {}).get("legacy", {})
                else:
                    continue
                
                if legacy and legacy.get("full_text"):
                    tweets.append({
                        "id": legacy.get("id_str"),
                        "text": legacy.get("full_text"),
                        "created_at": legacy.get("created_at"),
                    })
    except (KeyError, TypeError):
        pass
    return tweets

def filter_daytrade_alerts(tweets: list[dict]) -> list[dict]:
    return [t for t in tweets if "#デイトレアラート" in t["text"]]

def parse_trade_signal(text: str) -> dict | None:
    code_match = re.search(r'\b(\d{4})\b', text)
    
    if "買い" in text or "ロング" in text or "BUY" in text.upper():
        action = "BUY"
    elif "売り" in text or "ショート" in text or "SELL" in text.upper():
        action = "SELL"
    else:
        action = None
    
    price_match = re.search(r'(\d{1,6}(?:,\d{3})*)円', text)
    price = int(price_match.group(1).replace(",", "")) if price_match else None
    
    if code_match and action:
        return {"code": code_match.group(1), "action": action, "price": price, "raw_text": text}
    return None

def analyze_with_groq(tweet_text: str) -> dict | None:
    from openai import OpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("OPENAI_API_BASE")
    model = os.getenv("OPENAI_MODEL", "llama-3.3-70b-versatile")
    
    if not api_key:
        print("❌ OPENAI_API_KEY が設定されていません")
        return None
    
    client = OpenAI(api_key=api_key, base_url=api_base)
    
    prompt = f"""以下のツイートから株取引のシグナルを抽出してください。

ツイート:
{tweet_text}

以下のJSON形式で回答してください（コードブロックなし、JSONのみ）:
{{"code": "銘柄コード（4桁）", "name": "銘柄名", "action": "BUY または SELL", "price": 目標価格（数値、不明なら null）, "confidence": 0.0〜1.0の信頼度, "reason": "判断理由"}}

取引シグナルが含まれていない場合は null と回答してください。"""
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        result_text = response.choices[0].message.content.strip()
        if result_text.lower() == "null":
            return None
        return json.loads(result_text)
    except Exception as e:
        print(f"❌ LLM解析エラー: {e}")
        return None

def format_for_moomoo(signal: dict) -> dict:
    """
    moomoo Python API (moomoo-api) の place_order 形式に変換
    参考: https://openapi.moomoo.com/moomoo-api-doc/en/trade/place-order.html
    """
    from enum import IntEnum
    
    # SDK 定数の簡易模倣（本番は moomoo.TrdEnv 等を利用）
    class TrdSide(IntEnum):
        BUY = 1
        SELL = 2
    
    class OrderType(IntEnum):
        NORMAL = 0      # 指値
        MARKET = 1      # 成行
    
    class TrdEnv(IntEnum):
        SIMULATE = 0    # ペーパートレード
        REAL = 1        # 本番
    
    class TimeInForce(IntEnum):
        DAY = 0         # 当日のみ
        GTC = 1         # キャンセルまで有効
    
    # 銘柄コード（日本株は JP.XXXX 形式）
    code = signal.get("code", "")
    market_code = f"JP.{code}"
    
    # 売買方向
    trd_side = TrdSide.BUY if signal.get("action") == "BUY" else TrdSide.SELL
    
    # 注文タイプ
    has_price = signal.get("price") is not None
    order_type = OrderType.NORMAL if has_price else OrderType.MARKET
    
    # 価格（成行でも必須なので0を設定）
    price = signal.get("price") if has_price else 0
    
    # place_order() の引数形式
    order_params = {
        "price": price,
        "qty": 100,  # 最小単元
        "code": market_code,
        "trd_side": trd_side,
        "order_type": order_type,
        "trd_env": TrdEnv.SIMULATE,  # .envのBROKER_ENVで切り替え可能に
        "time_in_force": TimeInForce.DAY,
        "remark": f"twitter_alert_{signal.get('code')}",
    }
    
    return {
        "params": order_params,
        "meta": {
            "source": "twitter_alert",
            "confidence": signal.get("confidence", 0.5),
            "original_code": code,
            "action": signal.get("action"),
            "reason": signal.get("reason", ""),
            "name": signal.get("name", ""),
        }
    }


def main():
    username = os.getenv("TWITTER_USERS", "snatchan_comm").split(",")[0].strip()
    
    print("=" * 60)
    print(f"@{username} の #デイトレアラート を取得・解析")
    print("=" * 60)
    
    data = fetch_latest_tweet(username)
    if not data:
        return
    
    tweets = extract_tweets(data)
    alerts = filter_daytrade_alerts(tweets)
    
    print(f"\n全ツイート: {len(tweets)}件")
    print(f"#デイトレアラート: {len(alerts)}件")
    
    if not alerts:
        print("\n#デイトレアラート が含まれるツイートがありません")
        print("\n最新ツイート（参考）:")
        for t in tweets[:3]:
            print(f"  - {t['text'][:60]}...")
        return
    
    print("\n" + "=" * 60)
    print("解析結果")
    print("=" * 60)
    
    for i, alert in enumerate(alerts[:3], 1):
        print(f"\n[{i}] {alert['created_at']}")
        print(f"    {alert['text'][:80]}...")
        
        signal = parse_trade_signal(alert["text"])
        
        if signal:
            print(f"\n    📊 正規表現で抽出:")
            print(f"       銘柄: {signal['code']}")
            print(f"       方向: {signal['action']}")
            print(f"       価格: {signal['price']}")
        else:
            print("\n    🤖 LLMで解析中...")
            signal = analyze_with_groq(alert["text"])
            
            if signal:
                print(f"       銘柄: {signal.get('code')} ({signal.get('name')})")
                print(f"       方向: {signal.get('action')}")
                print(f"       価格: {signal.get('price')}")
                print(f"       信頼度: {signal.get('confidence')}")
                print(f"       理由: {signal.get('reason')}")
        
        # ここで抽出/解析されたシグナルを、別のブローカー連携ロジックに渡せる

if __name__ == "__main__":
    main()
