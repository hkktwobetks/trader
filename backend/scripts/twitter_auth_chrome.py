#!/usr/bin/env python3
"""
Twitter Cookie 取得スクリプト（既存Chrome使用版）

手順：
1. 開いているChromeをすべて閉じる
2. このスクリプトを実行
3. 新しく開いたChromeでTwitterにログイン（Googleログイン可）
4. ホーム画面到達でCookie自動取得

※ これはPlaywrightではなく、あなたの通常のChromeを使います
※ Googleに「安全でない」と判定されません
"""

import asyncio
import json
import subprocess
import sys
import os
from pathlib import Path

# Chrome DevTools Protocol でCookieを取得
COOKIES_FILE = Path(__file__).parent.parent / ".twitter_cookies.json"
ENV_FILE = Path(__file__).parent.parent / ".env.twitter"


def get_chrome_path():
    """Chromeのパスを取得"""
    candidates = [
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


async def main():
    print("=" * 50)
    print("Twitter Cookie 取得（Chrome使用版）")
    print("=" * 50)
    print()
    
    chrome_path = get_chrome_path()
    if not chrome_path:
        print("❌ Chromeが見つかりません")
        print("   google-chrome または chromium をインストールしてください")
        sys.exit(1)
    
    print(f"Chrome: {chrome_path}")
    print()
    print("⚠️  開いているChromeをすべて閉じてください")
    print()
    input("準備ができたらEnterを押してください...")
    
    # デバッグポート付きでChromeを起動
    debug_port = 9222
    user_data_dir = Path(__file__).parent.parent / ".chrome_profile"
    user_data_dir.mkdir(exist_ok=True)
    
    print()
    print("🚀 Chromeを起動中...")
    
    proc = subprocess.Popen([
        chrome_path,
        f"--remote-debugging-port={debug_port}",
        f"--user-data-dir={user_data_dir}",
        "https://twitter.com/login"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    await asyncio.sleep(3)
    
    print()
    print("📱 ブラウザでTwitterにログインしてください")
    print("   （Googleログインを使用できます）")
    print()
    print("ログイン完了後、Enterを押してください...")
    input()
    
    # Playwrightで接続してCookieを取得
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
            context = browser.contexts[0]
            
            cookies = await context.cookies()
            cookie_dict = {c["name"]: c["value"] for c in cookies}
            
            auth_token = cookie_dict.get("auth_token", "")
            ct0 = cookie_dict.get("ct0", "")
            
            if auth_token and ct0:
                print()
                print("=" * 50)
                print("✅ Cookie取得成功！")
                print("=" * 50)
                print(f"X_AUTH_TOKEN={auth_token}")
                print(f"X_CT0={ct0}")
                
                COOKIES_FILE.write_text(json.dumps(cookies, indent=2))
                ENV_FILE.write_text(f"X_AUTH_TOKEN={auth_token}\nX_CT0={ct0}\n")
                
                print()
                print(f"保存先: {ENV_FILE}")
            else:
                print()
                print("❌ Cookie取得失敗")
                print(f"取得できたCookie: {list(cookie_dict.keys())}")
                print("ログインが完了しているか確認してください")
            
            await browser.close()
    
    except Exception as e:
        print(f"❌ エラー: {e}")
    
    finally:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
