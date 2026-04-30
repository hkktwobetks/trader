import socket
from typing import cast

from app.config import settings

from .base import Broker
from .paper import PaperBroker

# (broker_name, broker_env) → Broker instance
_cache: dict[tuple[str, str], Broker] = {}


def _is_host_reachable(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _build_broker(broker_name: str, broker_env: str) -> Broker:
    if broker_name == "moomoo":
        from .moomoo_client import MoomooBroker
        return MoomooBroker(
            host=settings.moomoo_opend_host,
            port=settings.moomoo_opend_port,
            trd_env=broker_env,
            rsa_private_key_path=settings.moomoo_rsa_private_key_path,
            acc_id=settings.moomoo_acc_id,
            market=settings.market,
            login_region=settings.moomoo_login_region,
            security_firm=settings.moomoo_security_firm,
            preferred_acc_type=settings.moomoo_preferred_acc_type,
            trade_password=settings.moomoo_trade_password,
            trade_password_md5=settings.moomoo_trade_password_md5,
        )
    if broker_name == "paper":
        return PaperBroker()
    raise ValueError(f"Unsupported broker '{broker_name}'. Update configuration.")


def get_broker(broker_name: str | None = None, broker_env: str | None = None) -> Broker:
    """Return a cached broker instance. Call reset_broker_cache() to force reconnection."""
    resolved_name = (broker_name or settings.broker).lower()
    resolved_env = (broker_env or settings.broker_env).upper()
    key = (resolved_name, resolved_env)
    if key not in _cache:
        if resolved_name == "moomoo" and not _is_host_reachable(
            settings.moomoo_opend_host, settings.moomoo_opend_port
        ):
            raise RuntimeError(
                f"Moomoo OpenD not reachable at {settings.moomoo_opend_host}:{settings.moomoo_opend_port}"
            )
        _cache[key] = cast(Broker, _build_broker(resolved_name, resolved_env))
    return _cache[key]


def reset_broker_cache() -> None:
    """Discard all cached broker instances so next call reconnects from scratch."""
    _cache.clear()


__all__ = ["get_broker", "reset_broker_cache", "Broker", "PaperBroker"]
