"""
Twitter Cookie の共有ストア

API プロセスと Worker プロセスの両方がアクセスできるように
ファイルベースで永続化する。
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional, Tuple

log = logging.getLogger(__name__)

_STORE_PATH = Path(os.getenv("COOKIE_STORE_PATH", "/tmp/twitter_cookies.json"))
_lock = threading.Lock()

# インメモリキャッシュ
_cache: dict = {}


def save_cookies(auth_token: str, ct0: str) -> None:
    """Cookie を保存（ファイル + メモリ）"""
    global _cache
    data = {"auth_token": auth_token, "ct0": ct0}
    with _lock:
        _cache = data
        try:
            _STORE_PATH.write_text(json.dumps(data))
        except Exception as e:
            log.warning(f"Cookie ファイル書き込み失敗: {e}")


def load_cookies() -> Tuple[str, str]:
    """Cookie を読み込み（メモリ → ファイル → 環境変数 の順）"""
    global _cache

    # 1. メモリキャッシュ
    if _cache.get("auth_token") and _cache.get("ct0"):
        return _cache["auth_token"], _cache["ct0"]

    # 2. ファイル
    with _lock:
        try:
            if _STORE_PATH.exists():
                data = json.loads(_STORE_PATH.read_text())
                if data.get("auth_token") and data.get("ct0"):
                    _cache = data
                    return data["auth_token"], data["ct0"]
        except Exception as e:
            log.warning(f"Cookie ファイル読み込み失敗: {e}")

    # 3. 環境変数フォールバック
    auth_token = os.getenv("X_AUTH_TOKEN", "")
    ct0 = os.getenv("X_CT0", "")
    if auth_token and ct0:
        _cache = {"auth_token": auth_token, "ct0": ct0}
    return auth_token, ct0


def get_version() -> Optional[str]:
    """Cookie の簡易バージョン（先頭8文字のハッシュ）"""
    auth_token, ct0 = load_cookies()
    if not auth_token:
        return None
    return auth_token[:8]
