#!/usr/bin/env python3
"""
Twitter Cookie 取得スクリプト（Firefox永続プロファイル版）

初回のみ手動でGoogleログインが必要。
2回目以降はログイン状態が保持されるので自動でCookieを取得できます。

FirefoxはGoogleの「安全でないブラウザ」判定を受けにくいです。
"""

import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from playwright.async_api import async_playwright

PROFILE_DIR = Path(__file__).parent.parent / ".firefox_profile"
COOKIES_FILE = Path(__file__).parent.parent / ".twitter_cookies.json"
ENV_FILE = Path(__file__).parent.parent / ".env.twitter"

TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD", "")


async def try_auto_google_login(page) -> bool:
    """Googleログインを自動で試行"""
    try:
        # Googleボタンを探してクリック
        google_btn = page.locator('text="Sign in with Google"').first
        if await google_btn.is_visible(timeout=5000):
            print("  → Googleログインボタンを発見、クリック中...")
            await google_btn.click()
            await asyncio.sleep(3)
            
            # Googleログインページでメールアドレスを入力
            email_input = page.locator('input[type="email"]')
            if await email_input.is_visible(timeout=10000):
                print("  → メールアドレスを入力中...")
                await email_input.fill(TWITTER_USERNAME)
                await page.locator('button:has-text("次へ"), #identifierNext').first.click()
                await asyncio.sleep(3)
                
                # パスワード入力
                password_input = page.locator('input[type="password"]')
                if await password_input.is_visible(timeout=10000):
                    print("  → パスワードを入力中...")
                    await password_input.fill(TWITTER_PASSWORD)
                    await page.locator('button:has-text("次へ"), #passwordNext').first.click()
                    await asyncio.sleep(5)
                    return True
    except Exception as e:
        print(f"  → 自動ログイン失敗: {e}")
    return False


async def main():
    print("=" * 50)
    print("Twitter Cookie 取得（Firefox版）")
    print("=" * 50)
    print()
    
    first_run = not PROFILE_DIR.exists()
    if first_run:
        print("🆕 初回起動です。プロファイルを作成します。")
    else:
        print("📂 既存のプロファイルを使用します。")
    print()
    
    async with async_playwright() as p:
        # Firefox永続プロファイル
        browser = await p.firefox.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            # Firefoxの設定
            firefox_user_prefs={
                "dom.webdriver.enabled": False,
                "useAutomationExtension": False,
            }
        )
        
        page = browser.pages[0] if browser.pages else await browser.new_page()
        
        print("[1/3] Twitterにアクセス中...")
        await page.goto("https://twitter.com/home")
        await asyncio.sleep(3)
        
        # ログインが必要か確認
        current_url = page.url
        if "login" in current_url or "flow" in current_url:
            print("[2/3] ログインが必要です...")
            
            # 自動ログインを試行
            if TWITTER_USERNAME and TWITTER_PASSWORD:
                print("  → 自動ログインを試行中...")
                success = await try_auto_google_login(page)
                if not success:
                    print("  → 自動ログイン失敗。手動でログインしてください。")
            else:
                print("  → 認証情報がありません。手動でログインしてください。")
            
            # ホーム画面を待機
            print("  ⏳ ホーム画面を待機中（最大5分）...")
            try:
                await page.wait_for_url("**/home", timeout=300000)
            except:
                pass
        else:
            print("[2/3] 既にログイン済み")
        
        await asyncio.sleep(2)
        print("[3/3] Cookieを取得中...")
        
        # Cookieを取得
        cookies = await browser.cookies()
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
            
            # .envにも追記
            env_path = Path(__file__).parent.parent / ".env"
            if env_path.exists():
                content = env_path.read_text()
                if "X_AUTH_TOKEN=xxxxx" in content:
                    content = content.replace("X_AUTH_TOKEN=xxxxx", f"X_AUTH_TOKEN={auth_token}")
                    content = content.replace("X_CT0=xxxxx", f"X_CT0={ct0}")
                    env_path.write_text(content)
                    print(f"✅ .env を更新しました")
            
            if first_run:
                print()
                print("💡 次回以降は自動でログイン状態が復元されます！")
        else:
            print()
            print("❌ Cookie取得失敗")
            print(f"取得できたCookie: {list(cookie_dict.keys())}")


if __name__ == "__main__":
    asyncio.run(main())
