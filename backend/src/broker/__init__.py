from functools import lru_cache
from typing import cast

from app.config import settings

from .base import Broker
from .paper import PaperBroker
from .moomoo_client import MoomooBroker


def _build_broker() -> Broker:
    broker_name = settings.broker.lower()
    if broker_name == "moomoo":
        return MoomooBroker(
            host=settings.moomoo_opend_host,
            port=settings.moomoo_opend_port,
            trd_env=settings.broker_env,
            acc_id=settings.moomoo_acc_id,
        )
    if broker_name == "paper":
        return PaperBroker()
    raise ValueError(f"Unsupported broker '{settings.broker}'. Update configuration.")


@lru_cache(maxsize=1)
def get_broker() -> Broker:
    """Return a singleton broker instance according to current settings."""
    return cast(Broker, _build_broker())


__all__ = ["get_broker", "Broker", "PaperBroker", "MoomooBroker"]
