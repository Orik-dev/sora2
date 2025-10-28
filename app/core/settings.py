# from pydantic_settings import BaseSettings, SettingsConfigDict
# from pydantic import Field
# from typing import Dict, Any, Optional

# class Settings(BaseSettings):
#     # Telegram
#     TELEGRAM_TOKEN: str
#     WEBHOOK_DOMAIN: str
#     WEBHOOK_SECRET: str

#     # Admin & debug
#     DEBUG: bool = False
#     ADMIN_ID: Optional[int] = None

#     # DB
#     DB_HOST: str
#     DB_PORT: int
#     DB_USER: str
#     DB_PASSWORD: str
#     DB_NAME: str

#     # Redis
#     REDIS_URL: str
#     REDIS_PASSWORD: str | None = None

#     # OpenAI / Sora
#     OPENAI_API_KEY: str
#     OPENAI_WEBHOOK_SECRET: str  # dashboard → Webhooks → signing secret
#     SORA_DEFAULT_MODEL: str = "sora-2"  # "sora-2" | "sora-2-pro"

#     # Billing
#     GENERATION_COST: int = 1

#     # YooKassa
#     YOOKASSA_SHOP_ID: Optional[str] = None
#     YOOKASSA_SECRET_KEY: Optional[str] = None
#     YOOKASSA_WEBHOOK_SECRET: Optional[str] = None
#     YOOKASSA_RECEIPT_ENABLED: bool = False
#     VAT_CODE: Optional[int] = None
#     TAX_SYSTEM_CODE: Optional[int] = None
#     RECEIPT_FALLBACK_EMAIL: Optional[str] = None

#     SUBSCRIPTION_PLANS_RUBS: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
#     SUBSCRIPTION_PLANS_STARS: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

#     # Greeting
#     GREETING_VIDEO_PATH: Optional[str] = "app/assets/welcome.mp4"
#     GREETING_IMAGE_URL: Optional[str] = None

#     # Examples/links (опционально)
#     EXAMPLES_URL: Optional[str] = None
#     GUIDE_URL: Optional[str] = None
#     SUPPORT_URL: Optional[str] = None

#     # Broadcast
#     BROADCAST_RPS: int = 25
#     BROADCAST_CONCURRENCY: int = 20
#     BROADCAST_BATCH: int = 1000

#     model_config = SettingsConfigDict(env_file=".env", extra="ignore")

#     @property
#     def SQLALCHEMY_URL(self) -> str:
#         return (
#             f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
#             f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
#             "?charset=utf8mb4"
#         )

#     def webhook_base(self) -> str:
#         return self.WEBHOOK_DOMAIN.rstrip("/")

# settings = Settings()


# app/core/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import Dict, Any, Optional

class Settings(BaseSettings):
    # Telegram
    TELEGRAM_TOKEN: str
    WEBHOOK_DOMAIN: str
    WEBHOOK_SECRET: str

    # Admin & debug
    DEBUG: bool = False
    ADMIN_ID: Optional[int] = None

    # DB
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    # Redis
    REDIS_URL: str
    REDIS_PASSWORD: str | None = None

    # Kie AI / Sora 2
    KIE_API_KEY: str
    KIE_BASE_URL: str = "https://api.kie.ai/api/v1"

    # Billing
    GENERATION_COST: int = 1

    # YooKassa
    YOOKASSA_SHOP_ID: Optional[str] = None
    YOOKASSA_SECRET_KEY: Optional[str] = None
    YOOKASSA_WEBHOOK_SECRET: Optional[str] = None
    YOOKASSA_RECEIPT_ENABLED: bool = False
    VAT_CODE: Optional[int] = None
    TAX_SYSTEM_CODE: Optional[int] = None
    RECEIPT_FALLBACK_EMAIL: Optional[str] = None

    SUBSCRIPTION_PLANS_RUBS: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    SUBSCRIPTION_PLANS_STARS: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    # Greeting
    GREETING_VIDEO_PATH: Optional[str] = "app/assets/welcome.mp4"
    GREETING_IMAGE_URL: Optional[str] = None

    # Examples/links (опционально)
    EXAMPLES_URL: Optional[str] = None
    GUIDE_URL: Optional[str] = None
    SUPPORT_URL: Optional[str] = None

    # Broadcast
    BROADCAST_RPS: int = 25
    BROADCAST_CONCURRENCY: int = 20
    BROADCAST_BATCH: int = 1000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def SQLALCHEMY_URL(self) -> str:
        return (
            f"mysql+aiomysql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            "?charset=utf8mb4"
        )

    def webhook_base(self) -> str:
        return self.WEBHOOK_DOMAIN.rstrip("/")

settings = Settings()