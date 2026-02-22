from abc import ABC, abstractmethod
from typing import Optional


class Broker(ABC):
    name: str


    @abstractmethod
    def place_order(
        self,
        ticker: str,
        side: str,
        qty: float,
        price: Optional[float] = None,
        order_type: str = "LIMIT",
        tif: str = "DAY",
    ) -> dict:
        ...


    @abstractmethod
    def positions(self) -> dict[str, dict]:
        ...


    @abstractmethod
    def cancel_all(self) -> None:
        ...
