from .base import Broker
from typing import Optional


class MoomooBroker(Broker):
    name = "moomoo"


    def __init__(self, host: str, port: int, account: str):
        # TODO: OpenD へ接続、ログイン、紙/本番アカウント確認
        self.host = host
        self.port = port
        self.account = account


    def place_order(self, ticker: str, side: str, qty: float, price: Optional[float] = None) -> dict:
        # TODO: moomoo SDK の注文APIを呼ぶ
        # ここではまだ未実装のため例外/ダミーを返す
        return {"status": "not_implemented"}


    def positions(self) -> dict[str, dict]:
        # TODO: 口座の保有一覧取得
        return {}


    def cancel_all(self) -> None:
        # TODO: すべての未約定注文をキャンセル
        return None