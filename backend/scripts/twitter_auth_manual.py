#!/usr/bin/env python3
"""
Twitter Cookie 手動ログイン取得スクリプト

ブラウザが開くので、手動でログインしてください。
ログイン完了後、自動的にCookieを取得します。
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

COOKIES_FILE = Path(__file__).parent.parent / ".twitter_cookies.json"
ENV_FILE = Path(__file__).parent.parent / ".env.twitter"


async def main():
    print("=" * 50)
    print("Twitter Cookie 手動ログイン取得")
    print("=" * 50)
    print()
    print("ブラウザが開きます。")
    print("手動でTwitterにログインしてください（Googleログイン可）")
    print("ホーム画面が表示されたら自動的にCookieを取得します。")
    print()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto("https://twitter.com/login")
        
        print("⏳ ログイン待機中... (ホーム画面に到達するまで待ちます)")
        print()
        
        # ホーム画面に到達するまで待つ（最大5分）
        try:
            await page.wait_for_url("**/home", timeout=300000)
        except:
            print("タイムアウトしましたが、現在のCookieを確認します...")
        
        await asyncio.sleep(2)
        
        # Cookieを取得
        cookies = await context.cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies}
        
        auth_token = cookie_dict.get("auth_token", "")
        ct0 = cookie_dict.get("ct0", "")
        
        await browser.close()
        
        if auth_token and ct0:
            print()
            print("=" * 50)
            print("✅ Cookie取得成功！")
            print("=" * 50)
            print(f"X_AUTH_TOKEN={auth_token}")
            print(f"X_CT0={ct0}")
            
            # ファイルに保存
            COOKIES_FILE.write_text(json.dumps(cookies, indent=2))
            ENV_FILE.write_text(f"X_AUTH_TOKEN={auth_token}\nX_CT0={ct0}\n")
            
            print()
            print(f"保存先: {ENV_FILE}")
        else:
            print()
            print("❌ Cookie取得失敗")
            print(f"取得できたCookie: {list(cookie_dict.keys())}")


if __name__ == "__main__":
    asyncio.run(main())
