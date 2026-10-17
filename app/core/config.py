from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://flyrank:flyrank_dev_password@localhost:5432/flyrank_billing"

    tenant_dev_token: str = "change-me-dev-token"

    public_base_url: str = "http://localhost:8000"
    checkout_success_url: str = "http://localhost:8000/docs?checkout=success"
    checkout_cancel_url: str = "http://localhost:8000/docs?checkout=cancel"

    pricing_version: str = "demo-v1"
    # DEMO rates in nano-USD per token. Not a live provider price list.
    # $3.00 / 1M fresh input, $0.30 / 1M cached input, $15.00 / 1M output.
    input_rate_nano_usd: int = 3_000
    cached_input_rate_nano_usd: int = 300
    output_rate_nano_usd: int = 15_000

    stripe_secret_key: str = "sk_test_placeholder"
    stripe_webhook_secret: str = "whsec_placeholder"
    stripe_pro_price_id: str = "price_placeholder"
    stripe_api_version: str = "2024-06-20"

    free_api_call_quota: int = 1_000
    free_ai_token_quota: int = 100_000
    pro_api_call_quota: int = 100_000
    pro_ai_token_quota: int = 10_000_000

    @field_validator("stripe_secret_key")
    @classmethod
    def reject_live_stripe_keys(cls, value: str) -> str:
        if value.startswith("sk_live_"):
            raise ValueError("Live Stripe keys are forbidden. Use TEST mode keys only (sk_test_...).")
        return value

    @property
    def stripe_configured(self) -> bool:
        return (
            self.stripe_secret_key.startswith("sk_test_")
            and self.stripe_secret_key != "sk_test_placeholder"
            and self.stripe_pro_price_id.startswith("price_")
            and self.stripe_pro_price_id != "price_placeholder"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
