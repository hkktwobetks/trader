from functools import lru_cache
from typing import cast

from app.config import settings

from .base import Broker
from .paper import PaperBroker
from .alpaca_client import AlpacaBroker


def _build_broker() -> Broker:
    broker_name = settings.broker.lower()
    if broker_name == "alpaca":
        return AlpacaBroker(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=settings.alpaca_paper,
        )
    if broker_name == "paper":
        return PaperBroker()
    raise ValueError(f"Unsupported broker '{settings.broker}'. Update configuration.")


@lru_cache(maxsize=1)
def get_broker() -> Broker:
    """Return a singleton broker instance according to current settings."""
    return cast(Broker, _build_broker())


__all__ = ["get_broker", "Broker", "PaperBroker", "AlpacaBroker"]
