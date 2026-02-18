"""
Twitter Cookieを手動で設定するスクリプト

使い方:
1. ブラウザでTwitter(x.com)にログイン
2. 開発者ツール(F12) > Application > Cookies > https://x.com
3. auth_token と ct0 の値をコピー
4. このスクリプトを実行して入力
"""
from pathlib import Path
from dotenv import set_key

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

def main():
    print("=" * 50)
    print("Twitter Cookie 手動設定ツール")
    print("=" * 50)
    print()
    print("ブラウザでx.comにログインし、開発者ツールからCookieを取得してください。")
    print("  1. F12で開発者ツールを開く")
    print("  2. Application > Cookies > https://x.com")
    print("  3. auth_token と ct0 をコピー")
    print()
    
    auth_token = input("auth_token を入力: ").strip()
    ct0 = input("ct0 を入力: ").strip()
    
    if not auth_token or not ct0:
        print("❌ 両方の値を入力してください")
        return
    
    set_key(str(ENV_PATH), "X_AUTH_TOKEN", auth_token)
    set_key(str(ENV_PATH), "X_CT0", ct0)
    
    print()
    print("✅ .env を更新しました")
    print(f"   X_AUTH_TOKEN={auth_token[:8]}...")
    print(f"   X_CT0={ct0[:8]}...")

if __name__ == "__main__":
    main()
