"""
moomoo API 接続テストスクリプト
OpenDが起動している必要があります
"""
import os
import sys
from pathlib import Path

# srcをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
from futu import OpenQuoteContext, OpenSecTradeContext, TrdEnv, TrdMarket

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

def test_quote_connection():
    """相場接続テスト"""
    host = os.getenv("MOOMOO_OPEND_HOST", "127.0.0.1")
    port = int(os.getenv("MOOMOO_OPEND_PORT", "11111"))
    
    print(f"📡 OpenD接続テスト: {host}:{port}")
    
    try:
        quote_ctx = OpenQuoteContext(host=host, port=port)
        ret, data = quote_ctx.get_global_state()
        
        if ret == 0:
            print("✅ 相場API接続成功")
            print(f"   状態: {data}")
        else:
            print(f"❌ 相場API接続失敗: {data}")
        
        quote_ctx.close()
        return ret == 0
    except Exception as e:
        print(f"❌ 接続エラー: {e}")
        return False

def test_trade_connection():
    """取引接続テスト"""
    host = os.getenv("MOOMOO_OPEND_HOST", "127.0.0.1")
    port = int(os.getenv("MOOMOO_OPEND_PORT", "11111"))
    broker_env = os.getenv("BROKER_ENV", "SIMULATE")
    
    trd_env = TrdEnv.SIMULATE if broker_env == "SIMULATE" else TrdEnv.REAL
    
    print(f"\n💹 取引API接続テスト (環境: {broker_env})")
    
    try:
        trd_ctx = OpenSecTradeContext(host=host, port=port)
        
        # アカウント一覧取得
        ret, data = trd_ctx.get_acc_list()
        if ret == 0:
            print("✅ 取引API接続成功")
            print(f"   アカウント一覧:")
            for acc in data.to_dict('records'):
                print(f"     - {acc}")
        else:
            print(f"❌ アカウント取得失敗: {data}")
            trd_ctx.close()
            return False
        
        # 日本株市場のアカウントを探す
        ret, data = trd_ctx.get_acc_list()
        if ret == 0:
            df = data
            jp_acc = df[df['trd_market_auth'].apply(lambda x: TrdMarket.JP in x if isinstance(x, list) else False)]
            if not jp_acc.empty:
                acc_id = jp_acc.iloc[0]['acc_id']
                print(f"\n   日本株アカウント: {acc_id}")
                
                # ポジション確認
                ret, data = trd_ctx.position_list_query(trd_env=trd_env)
                if ret == 0:
                    print(f"   ポジション: {len(data)}件")
                
                # 注文履歴確認
                ret, data = trd_ctx.order_list_query(trd_env=trd_env)
                if ret == 0:
                    print(f"   注文履歴: {len(data)}件")
        
        trd_ctx.close()
        return True
    except Exception as e:
        print(f"❌ 取引接続エラー: {e}")
        return False

def test_stock_quote():
    """株価取得テスト"""
    host = os.getenv("MOOMOO_OPEND_HOST", "127.0.0.1")
    port = int(os.getenv("MOOMOO_OPEND_PORT", "11111"))
    
    print(f"\n📈 株価取得テスト")
    
    try:
        quote_ctx = OpenQuoteContext(host=host, port=port)
        
        # 日本株のテスト（ソフトバンクグループ）
        ret, data = quote_ctx.get_stock_quote(["JP.9984"])
        
        if ret == 0:
            print("✅ 株価取得成功")
            for _, row in data.iterrows():
                print(f"   {row['code']}: {row['last_price']}円")
        else:
            print(f"❌ 株価取得失敗: {data}")
        
        quote_ctx.close()
        return ret == 0
    except Exception as e:
        print(f"❌ 株価取得エラー: {e}")
        return False

def main():
    print("=" * 60)
    print("moomoo API 接続テスト")
    print("=" * 60)
    print()
    print("※ Docker で OpenD を起動してください:")
    print("   docker-compose up -d opend")
    print()
    
    quote_ok = test_quote_connection()
    trade_ok = test_trade_connection()
    stock_ok = test_stock_quote() if quote_ok else False
    
    print()
    print("=" * 60)
    print("結果サマリ")
    print("=" * 60)
    print(f"  相場API:   {'✅ OK' if quote_ok else '❌ NG'}")
    print(f"  取引API:   {'✅ OK' if trade_ok else '❌ NG'}")
    print(f"  株価取得:  {'✅ OK' if stock_ok else '❌ NG'}")
    
    if not quote_ok:
        print()
        print("⚠️ OpenDが起動していない可能性があります")
        print("   moomooアプリを起動し、OpenDを有効化してください")

if __name__ == "__main__":
    main()
