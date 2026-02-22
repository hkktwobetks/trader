"""
Twitter認証ヘルパー

Cookieの読み込み・検証・自動更新を管理
"""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

log = logging.getLogger(__name__)

COOKIES_FILE = Path(__file__).parent.parent.parent / ".twitter_cookies.json"
ENV_FILE = Path(__file__).parent.parent.parent / ".env.twitter"


def load_cookies_from_file() -> Tuple[str, str]:
    """保存されたCookieファイルから読み込み"""
    if not COOKIES_FILE.exists():
        return "", ""
    
    try:
        cookies = json.loads(COOKIES_FILE.read_text())
        cookie_dict = {c["name"]: c["value"] for c in cookies}
        return cookie_dict.get("auth_token", ""), cookie_dict.get("ct0", "")
    except Exception as e:
        log.warning(f"Cookieファイルの読み込みに失敗: {e}")
        return "", ""


def load_cookies_from_env() -> Tuple[str, str]:
    """環境変数から読み込み"""
    return os.getenv("X_AUTH_TOKEN", ""), os.getenv("X_CT0", "")


def get_twitter_cookies(auto_refresh: bool = True) -> Tuple[str, str]:
    """
    Twitter Cookieを取得
    
    優先順位:
    1. 環境変数
    2. .twitter_cookies.json ファイル
    3. 自動取得（auto_refresh=True の場合）
    """
    # 環境変数を優先
    auth_token, ct0 = load_cookies_from_env()
    if auth_token and ct0:
        log.debug("環境変数からCookieを使用")
        return auth_token, ct0
    
    # ファイルから読み込み
    auth_token, ct0 = load_cookies_from_file()
    if auth_token and ct0:
        log.debug("ファイルからCookieを使用")
        return auth_token, ct0
    
    # 自動取得
    if auto_refresh:
        log.info("Cookieが見つかりません。自動取得を試みます...")
        if refresh_cookies():
            return load_cookies_from_file()
    
    return "", ""


def refresh_cookies() -> bool:
    """
    Cookieを再取得
    
    scripts/twitter_auth.py を実行
    """
    auth_script = Path(__file__).parent.parent.parent / "scripts" / "twitter_auth.py"
    
    if not auth_script.exists():
        log.error(f"認証スクリプトが見つかりません: {auth_script}")
        return False
    
    # 必要な環境変数チェック
    if not os.getenv("TWITTER_USERNAME") or not os.getenv("TWITTER_PASSWORD"):
        log.error("TWITTER_USERNAME と TWITTER_PASSWORD が必要です")
        return False
    
    try:
        result = subprocess.run(
            [sys.executable, str(auth_script)],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "HEADLESS": "true"},
        )
        
        if result.returncode != 0:
            log.error(f"認証スクリプトが失敗: {result.stderr}")
            return False
        
        log.info("Cookie更新成功")
        return True
        
    except subprocess.TimeoutExpired:
        log.error("認証スクリプトがタイムアウト")
        return False
    except Exception as e:
        log.error(f"認証スクリプト実行エラー: {e}")
        return False


def validate_cookies(auth_token: str, ct0: str) -> bool:
    """
    Cookieが有効かどうかを簡易チェック
    
    実際のAPIリクエストで検証（オプション）
    """
    if not auth_token or not ct0:
        return False
    
    # 基本的な形式チェック
    if len(auth_token) < 20 or len(ct0) < 20:
        return False
    
    return True
