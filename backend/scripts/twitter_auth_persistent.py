#!/usr/bin/env python3
"""
Twitter Cookie 取得スクリプト（永続プロファイル版）

初回のみ手動でGoogleログインが必要。
2回目以降はログイン状態が保持されるので自動でCookieを取得できます。
"""

import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright

PROFILE_DIR = Path(__file__).parent.parent / ".playwright_profile"
COOKIES_FILE = Path(__file__).parent.parent / ".twitter_cookies.json"
ENV_FILE = Path(__file__).parent.parent / ".env.twitter"


async def main():
    print("=" * 50)
    print("Twitter Cookie 取得（永続プロファイル版）")
    print("=" * 50)
    print()
    
    first_run = not PROFILE_DIR.exists()
    if first_run:
        print("🆕 初回起動です。")
        print("   ブラウザが開いたら、Googleでログインしてください。")
        print("   ログイン状態は保存され、次回以降は自動になります。")
    else:
        print("📂 既存のプロファイルを使用します。")
    print()
    
    async with async_playwright() as p:
        # 永続的なコンテキスト（プロファイル）を使用
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            channel="chromium",  # または "chrome" でインストール済みChromeを使用
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Twitterにアクセス
        await page.goto("https://twitter.com/home")
        await asyncio.sleep(2)
        
        # ログインページにリダイレクトされたか確認
        current_url = page.url
        if "login" in current_url or "flow" in current_url:
            print("⏳ ログインが必要です。ブラウザでログインしてください...")
            print("   （ホーム画面に到達するまで待機します）")
            
            try:
                await page.wait_for_url("**/home", timeout=300000)  # 5分待機
            except:
                pass
        
        await asyncio.sleep(2)
        
        # 現在のURLを確認
        current_url = page.url
        print(f"現在のURL: {current_url}")
        
        # Cookieを取得
        cookies = await context.cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies}
        
        auth_token = cookie_dict.get("auth_token", "")
        ct0 = cookie_dict.get("ct0", "")
        
        await context.close()
        
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
            print()
            if first_run:
                print("💡 次回以降は自動でログイン状態が復元されます！")
        else:
            print()
            print("❌ Cookie取得失敗")
            print(f"取得できたCookie: {list(cookie_dict.keys())}")
            print()
            print("もう一度実行してログインを完了してください。")


if __name__ == "__main__":
    asyncio.run(main())
