"""
moomoo API 接続テストスクリプト
OpenD が起動し、API ポート（既定 11111）が開いている必要があります。
"""
from __future__ import annotations

import os
import socket
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
from moomoo import RET_OK, OpenQuoteContext, OpenSecTradeContext, SubType, TrdEnv, TrdMarket

from broker.moomoo_sdk import configure_sdk_encryption

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local", override=True)


def _running_inside_docker() -> bool:
    try:
        return Path("/.dockerenv").is_file()
    except OSError:
        return False


def _host_port() -> tuple[str, int]:
    """接続先。MOOMOO_OPEND_FORCE_HOST があれば最優先。"""
    forced = os.getenv("MOOMOO_OPEND_FORCE_HOST", "").strip()
    if forced:
        return forced, int(os.getenv("MOOMOO_OPEND_PORT", "11111"))

    host = os.getenv("MOOMOO_OPEND_HOST", "127.0.0.1")
    port = int(os.getenv("MOOMOO_OPEND_PORT", "11111"))

    # .env が backend コンテナ用に opend になっているとき、ホスト上の uv run では解決できない
    if not _running_inside_docker() and host in ("opend", "moomoo-opend"):
        print(
            "ℹ️  MOOMOO_OPEND_HOST=opend は Docker ネットワーク内のホスト名です。"
            "ホストから接続テストするため 127.0.0.1 に切り替えます（ポート転送 11111 前提）。"
        )
        host = "127.0.0.1"

    return host, port


def check_opend_tcp_reachable(timeout_sec: float | None = None) -> bool:
    """OpenD の API ポートに素早く TCP 接続できるか（SDK より先に失敗させる）。"""
    host, port = _host_port()
    t = timeout_sec if timeout_sec is not None else float(os.getenv("MOOMOO_TCP_CHECK_TIMEOUT", "3"))
    try:
        with socket.create_connection((host, int(port)), timeout=t):
            return True
    except OSError:
        return False


def _print_tcp_failure_help() -> None:
    host, port = _host_port()
    print()
    print(f"❌ {host}:{port} に TCP で接続できませんでした（OpenD が待ち受けていないか、ホスト指定が誤りです）。")
    print()
    print("対処例:")
    print("  ・公式 moomoo OpenD を起動し、API ポートが 11111 か確認する")
    print("  ・同一 PC 上なら backend/.env で  MOOMOO_OPEND_HOST=127.0.0.1")
    print("  ・Docker compose で opend コンテナと一緒に動かすなら  MOOMOO_OPEND_HOST=opend（api コンテナ内から）")
    print("  ・WSL から Windows ホストの OpenD へ繋ぐ場合は、実際にポート転送されている IP を指定")
    print("    （.env に古い 172.x のまま残っているとタイムアウトしやすいです）")


def _api_phase_timeout_sec() -> float:
    return float(os.getenv("MOOMOO_API_TEST_TIMEOUT", "25"))


def _quote_context():
    host, port = _host_port()
    is_encrypt = configure_sdk_encryption(os.getenv("MOOMOO_RSA_PRIVATE_KEY_PATH", "").strip())
    return OpenQuoteContext(host=host, port=port, is_encrypt=is_encrypt)


def _trade_context():
    host, port = _host_port()
    is_encrypt = configure_sdk_encryption(os.getenv("MOOMOO_RSA_PRIVATE_KEY_PATH", "").strip())
    return OpenSecTradeContext(host=host, port=port, is_encrypt=is_encrypt)


def _run_timed_phase(phase_name: str, fn) -> bool:
    """SDK が無限リトライしないよう、フェーズ単位で上限時間を設ける。"""
    sec = _api_phase_timeout_sec()
    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        try:
            return bool(fut.result(timeout=sec))
        except FuturesTimeout:
            print(f"\n❌ 「{phase_name}」が {sec}s 以内に完了しませんでした。")
            print("   OpenD が起動・ログイン済みか、11111 が OpenD 以外に使われていないか確認してください。")
            print("   待ち時間を延ばす: MOOMOO_API_TEST_TIMEOUT=60")
            return False


def test_quote_connection() -> bool:
    """相場接続テスト"""
    host, port = _host_port()

    print(f"📡 OpenD 相場API: {host}:{port}")

    try:
        quote_ctx = _quote_context()
        ret, data = quote_ctx.get_global_state()

        if ret == RET_OK:
            print("✅ 相場API接続成功")
            print(f"   状態: {data}")
        else:
            print(f"❌ 相場API接続失敗: {data}")

        quote_ctx.close()
        return ret == RET_OK
    except Exception as e:
        print(f"❌ 接続エラー: {e}")
        return False


def test_trade_connection() -> bool:
    """取引接続テスト"""
    host, port = _host_port()
    broker_env = os.getenv("BROKER_ENV", "SIMULATE")

    trd_env = TrdEnv.SIMULATE if broker_env == "SIMULATE" else TrdEnv.REAL

    print(f"\n💹 取引API (環境: {broker_env})")

    try:
        trd_ctx = _trade_context()

        ret, data = trd_ctx.get_acc_list()
        if ret == RET_OK:
            print("✅ 取引API接続成功")
            print("   アカウント一覧:")
            for acc in data.to_dict("records"):
                print(f"     - {acc}")
        else:
            print(f"❌ アカウント取得失敗: {data}")
            trd_ctx.close()
            return False

        ret, data = trd_ctx.get_acc_list()
        if ret == RET_OK:
            df = data
            if "trd_market_auth" in df.columns:
                jp_acc = df[
                    df["trd_market_auth"].apply(
                        lambda x: TrdMarket.JP in x if isinstance(x, list) else False
                    )
                ]
                if not jp_acc.empty:
                    acc_id = int(jp_acc.iloc[0]["acc_id"])
                    print(f"\n   日本株アカウント: {acc_id}")

                    ret, data = trd_ctx.position_list_query(trd_env=trd_env, acc_id=acc_id)
                    if ret == RET_OK:
                        print(f"   ポジション: {len(data)}件")

                    ret, data = trd_ctx.order_list_query(trd_env=trd_env, acc_id=acc_id)
                    if ret == RET_OK:
                        print(f"   注文履歴: {len(data)}件")
            else:
                print("   補足: acc_list に trd_market_auth 列が無いため、市場別の追加確認はスキップしました。")

        trd_ctx.close()
        return True
    except Exception as e:
        print(f"❌ 取引接続エラー: {e}")
        return False


def test_stock_quote() -> bool:
    """1 銘柄の株価取得（MARKET に応じたコード）"""
    host, port = _host_port()
    market = (os.getenv("MARKET", "US") or "US").upper()
    code = "JP.9984" if market == "JP" else "US.AAPL"

    print(f"\n📈 株価取得テスト ({code})")

    try:
        quote_ctx = _quote_context()
        ret, data = quote_ctx.subscribe([code], [SubType.QUOTE], subscribe_push=False)
        if ret != RET_OK:
            print(f"❌ quote購読失敗: {data}")
            quote_ctx.close()
            return False
        ret, data = quote_ctx.get_stock_quote([code])

        if ret == RET_OK:
            print("✅ 株価取得成功")
            for _, row in data.iterrows():
                print(f"   {row['code']}: {row['last_price']}")
        else:
            print(f"❌ 株価取得失敗: {data}")

        quote_ctx.close()
        return ret == RET_OK
    except Exception as e:
        print(f"❌ 株価取得エラー: {e}")
        return False


def main() -> None:
    print("=" * 60)
    print("moomoo / OpenD 接続テスト")
    print("=" * 60)
    print()
    host, port = _host_port()
    print(f"接続先: MOOMOO_OPEND_HOST={host}  MOOMOO_OPEND_PORT={port}")
    print()
    print("※ 先に OpenD を起動してください（例: docker compose --profile moomoo up -d）")
    print("   または公式デスクトップ OpenD で 127.0.0.1:11111")
    print()

    if not check_opend_tcp_reachable():
        _print_tcp_failure_help()
        raise SystemExit(1)

    print(f"✅ TCP {host}:{port} は開いています → SDK で本番チェックします")
    print("   （他アプリが 11111 を占有していると TCP は成功しても SDK が失敗することがあります）\n")

    quote_ok = _run_timed_phase("相場API", test_quote_connection)
    # 相場が通らない状態で取引だけ成功することはないのでスキップ（別スレッドの SDK ログも抑える）
    trade_ok = _run_timed_phase("取引API", test_trade_connection) if quote_ok else False
    stock_ok = _run_timed_phase("株価取得", test_stock_quote) if quote_ok else False

    print()
    print("=" * 60)
    print("結果サマリ")
    print("=" * 60)
    print(f"  相場API:   {'✅ OK' if quote_ok else '❌ NG'}")
    print(f"  取引API:   {'✅ OK' if trade_ok else '❌ NG'}")
    print(f"  株価取得:  {'✅ OK' if stock_ok else '❌ NG'}  (MARKET={os.getenv('MARKET', 'US')})")

    if not quote_ok:
        print()
        print("⚠️ 相場API が失敗した場合は、OpenD のログイン・規約同意・Connected 表示を確認してください。")

    raise SystemExit(0 if quote_ok and trade_ok else 1)


if __name__ == "__main__":
    main()
