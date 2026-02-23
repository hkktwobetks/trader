import os
from typing import Optional

from pydantic import BaseModel


class Settings(BaseModel):
    discord_bot_token: str = os.getenv("DISCORD_BOT_TOKEN", "")
    discord_target_channel_ids: list[int] = [
    int(x) for x in os.getenv("DISCORD_TARGET_CHANNEL_IDS", "").split(",") if x
    ]


    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_api_base: str = os.getenv("OPENAI_API_BASE", "")  # Groq: https://api.groq.com/openai/v1
    openai_model: str = os.getenv("OPENAI_MODEL", "llama-3.3-70b-versatile")  # Groq無料モデル


    max_daily_loss: float = float(os.getenv("MAX_DAILY_LOSS", "500"))
    max_position_per_ticker: int = int(os.getenv("MAX_POSITION_PER_TICKER", "2"))
    default_order_usd: float = float(os.getenv("DEFAULT_ORDER_USD", "200"))
    market: str = os.getenv("MARKET", "US")

    # 自動取引設定
    auto_trade_enabled: bool = os.getenv("AUTO_TRADE_ENABLED", "false").lower() == "true"
    min_confidence: float = float(os.getenv("MIN_CONFIDENCE", "0.7"))


    broker: str = os.getenv("BROKER", "paper") # paper or alpaca
    # Alpaca
    alpaca_api_key: str = os.getenv("ALPACA_API_KEY", "")
    alpaca_secret_key: str = os.getenv("ALPACA_SECRET_KEY", "")
    alpaca_paper: bool = os.getenv("ALPACA_PAPER", "true").lower() == "true"


    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./trader.db")


settings = Settings()
