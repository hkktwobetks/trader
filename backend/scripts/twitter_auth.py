#!/usr/bin/env python3
"""
Twitter Cookie 自動取得スクリプト

環境変数:
  TWITTER_USERNAME: Twitterのユーザー名/メール/電話番号 または Googleメールアドレス
  TWITTER_PASSWORD: Twitterのパスワード または Googleパスワード
  TWITTER_LOGIN_METHOD: "google" または "normal"（デフォルト: normal）

使用方法:
  uv add playwright
  playwright install chromium
  uv run python scripts/twitter_auth.py

出力:
  成功時は auth_token と ct0 を標準出力に表示し、.env.twitter ファイルに保存
"""

import asyncio
import os
import sys
import json
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("Error: playwright がインストールされていません")
    print("  uv add playwright")
    print("  playwright install chromium")
    sys.exit(1)

TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD", "")
LOGIN_METHOD = os.getenv("TWITTER_LOGIN_METHOD", "normal").lower()  # "google" or "normal"

COOKIES_FILE = Path(__file__).parent.parent / ".twitter_cookies.json"
ENV_FILE = Path(__file__).parent.parent / ".env.twitter"


async def login_with_google(page) -> None:
    """Googleアカウントでログイン"""
    print("[2/4] Googleでログインを選択中...")
    
    # デバッグ用スクリーンショット
    await page.screenshot(path="debug_login_page.png")
    print("  デバッグ: debug_login_page.png を保存しました")
    
    # Twitterの「Googleでログイン」ボタンを探す（複数のセレクタを試す）
    google_selectors = [
        # 英語版
        'button:has-text("Sign in with Google")',
        '[role="button"]:has-text("Sign in with Google")',
        # ソーシャルログインボタン（アイコン付き）
        '[data-testid="google_sign_in_button"]',
        'button[aria-label*="Google"]',
        'div[role="button"]:has-text("Google")',
        'button:has-text("Googleで登録")',
        'button:has-text("Googleでログイン")',
        'button:has-text("Google")',
        # iframeの場合
        'iframe[src*="accounts.google.com"]',
    ]
    
    google_button = None
    for selector in google_selectors:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=2000):
                google_button = btn
                print(f"  Googleボタンを発見: {selector}")
                break
        except:
            continue
    
    if not google_button:
        # ページ内のすべてのボタンを表示
        buttons = await page.locator('button, [role="button"]').all()
        print(f"  見つかったボタン数: {len(buttons)}")
        for i, btn in enumerate(buttons[:10]):
            text = await btn.text_content()
            print(f"    [{i}] {text[:50] if text else '(empty)'}")
        raise ValueError("Googleログインボタンが見つかりません。debug_login_page.png を確認してください")
    
    await google_button.click()
    await asyncio.sleep(3)
    
    # Googleのポップアップまたはリダイレクトを待つ
    pages = page.context.pages
    if len(pages) > 1:
        # ポップアップが開いた場合
        popup = pages[-1]
        print("  Googleポップアップを検出")
        await handle_google_login(popup)
    else:
        # 同じページ内でリダイレクト
        await handle_google_login(page)


async def handle_google_login(page) -> None:
    """Googleログインフォームを処理"""
    print("[2.5/4] Googleアカウント情報を入力中...")
    
    # メールアドレス入力
    email_input = page.locator('input[type="email"]')
    await email_input.wait_for(state="visible", timeout=15000)
    await email_input.fill(TWITTER_USERNAME)
    await page.locator('button:has-text("次へ"), #identifierNext').click()
    await asyncio.sleep(2)
    
    # パスワード入力
    password_input = page.locator('input[type="password"]')
    await password_input.wait_for(state="visible", timeout=10000)
    await password_input.fill(TWITTER_PASSWORD)
    await page.locator('button:has-text("次へ"), #passwordNext').click()
    await asyncio.sleep(3)


async def login_normal(page) -> None:
    """通常のTwitterログイン"""
    # ユーザー名入力
    print("[2/4] ユーザー名を入力中...")
    username_input = page.locator('input[autocomplete="username"]')
    await username_input.wait_for(state="visible", timeout=15000)
    await username_input.fill(TWITTER_USERNAME)
    await page.keyboard.press("Enter")
    await asyncio.sleep(2)
    
    # 追加確認（電話番号/ユーザー名の確認が求められる場合）
    try:
        unusual_activity = page.locator('input[data-testid="ocfEnterTextTextInput"]')
        if await unusual_activity.is_visible(timeout=3000):
            print("[2.5/4] 追加確認を入力中...")
            await unusual_activity.fill(TWITTER_USERNAME)
            await page.keyboard.press("Enter")
            await asyncio.sleep(2)
    except PlaywrightTimeout:
        pass
    
    # パスワード入力
    print("[3/4] パスワードを入力中...")
    password_input = page.locator('input[name="password"]')
    await password_input.wait_for(state="visible", timeout=10000)
    await password_input.fill(TWITTER_PASSWORD)
    await page.keyboard.press("Enter")
    await asyncio.sleep(3)


async def login_twitter() -> dict[str, str]:
    """Playwrightでログインし、auth_tokenとct0を取得"""
    
    if not TWITTER_USERNAME or not TWITTER_PASSWORD:
        raise ValueError("TWITTER_USERNAME と TWITTER_PASSWORD を環境変数に設定してください")
    
    async with async_playwright() as p:
        # ブラウザ起動（ヘッドレスはGoogleログインで問題が起きやすいのでデフォルトfalse）
        headless = os.getenv("HEADLESS", "false" if LOGIN_METHOD == "google" else "true").lower() == "true"
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            print(f"[1/4] Twitter ログインページにアクセス中... (方式: {LOGIN_METHOD})")
            await page.goto("https://twitter.com/i/flow/login", wait_until="networkidle")
            await asyncio.sleep(2)
            
            if LOGIN_METHOD == "google":
                await login_with_google(page)
            else:
                await login_normal(page)
            
            # ログイン完了待機
            print("[4/4] ログイン完了を確認中...")
            await page.wait_for_url("**/home", timeout=60000)
            await asyncio.sleep(2)
            
            # Cookieを取得
            cookies = await context.cookies()
            cookie_dict = {c["name"]: c["value"] for c in cookies}
            
            auth_token = cookie_dict.get("auth_token", "")
            ct0 = cookie_dict.get("ct0", "")
            
            if not auth_token or not ct0:
                # Cookie一覧をデバッグ出力
                print("取得できたCookie:", list(cookie_dict.keys()))
                raise ValueError("auth_token または ct0 が取得できませんでした")
            
            # Cookieをファイルに保存
            COOKIES_FILE.write_text(json.dumps(cookies, indent=2))
            print(f"Cookieを保存しました: {COOKIES_FILE}")
            
            return {"auth_token": auth_token, "ct0": ct0}
            
        except PlaywrightTimeout as e:
            # スクリーンショットを保存
            screenshot_path = Path(__file__).parent.parent / "login_error.png"
            await page.screenshot(path=str(screenshot_path))
            print(f"エラー発生。スクリーンショット保存: {screenshot_path}")
            raise RuntimeError(f"ログイン中にタイムアウト: {e}")
        finally:
            await browser.close()


def save_env_file(auth_token: str, ct0: str) -> None:
    """環境変数ファイルに保存"""
    content = f"""# Twitter認証情報（自動生成）
X_AUTH_TOKEN={auth_token}
X_CT0={ct0}
"""
    ENV_FILE.write_text(content)
    print(f"環境変数ファイルを保存しました: {ENV_FILE}")


async def main():
    print("=" * 50)
    print("Twitter Cookie 自動取得スクリプト")
    print("=" * 50)
    
    try:
        result = await login_twitter()
        
        print("\n" + "=" * 50)
        print("✅ ログイン成功！")
        print("=" * 50)
        print(f"X_AUTH_TOKEN={result['auth_token']}")
        print(f"X_CT0={result['ct0']}")
        
        save_env_file(result["auth_token"], result["ct0"])
        
        print("\n次のステップ:")
        print("  1. .env に上記の値を追加するか、")
        print("  2. docker-compose.yml で env_file に .env.twitter を追加してください")
        
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
