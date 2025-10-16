from pydantic import BaseModel
import os


class Settings(BaseModel):
    discord_bot_token: str = os.getenv("DISCORD_BOT_TOKEN", "")
    discord_target_channel_ids: list[int] = [
    int(x) for x in os.getenv("DISCORD_TARGET_CHANNEL_IDS", "").split(",") if x
    ]


    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


    max_daily_loss: float = float(os.getenv("MAX_DAILY_LOSS", "500"))
    max_position_per_ticker: int = int(os.getenv("MAX_POSITION_PER_TICKER", "2"))
    default_order_usd: float = float(os.getenv("DEFAULT_ORDER_USD", "200"))
    market: str = os.getenv("MARKET", "US")


    broker: str = os.getenv("BROKER", "paper") # paper or moomoo
    # moomoo placeholders
    moomoo_opend_host: str = os.getenv("MOOMOO_OPEND_HOST", "127.0.0.1")
    moomoo_opend_port: int = int(os.getenv("MOOMOO_OPEND_PORT", "11111"))
    moomoo_paper_account: str = os.getenv("MOOMOO_PAPER_ACCOUNT", "SIMULATE")


    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./trader.db")


settings = Settings()