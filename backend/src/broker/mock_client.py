"""
moomoo APIのモッククライアント（開発・テスト用）
"""
import random
from datetime import datetime

class MockMoomooClient:
    def __init__(self):
        self.orders = []
        self.positions = []
        print("📝 MockMoomooClient 初期化（モック モード）")
    
    def place_order(self, code: str, trd_side: int, qty: int, price: float = 0, **kwargs) -> dict:
        """模擬注文"""
        order_id = f"MOCK_{random.randint(100000, 999999)}"
        order = {
            "order_id": order_id,
            "code": code,
            "trd_side": "BUY" if trd_side == 1 else "SELL",
            "qty": qty,
            "price": price,
            "status": "SUBMITTED",
            "created_at": datetime.now().isoformat(),
        }
        self.orders.append(order)
        print(f"📤 模擬注文: {order}")
        return order
    
    def get_positions(self) -> list:
        return self.positions
    
    def get_orders(self) -> list:
        return self.orders
    
    def get_quote(self, code: str) -> dict:
        """模擬株価"""
        return {
            "code": code,
            "last_price": random.uniform(1000, 5000),
            "bid_price": random.uniform(1000, 5000),
            "ask_price": random.uniform(1000, 5000),
        }
