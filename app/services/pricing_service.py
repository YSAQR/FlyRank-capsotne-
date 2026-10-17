from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.core.exceptions import ValidationAppError


@dataclass(frozen=True)
class TokenUsage:
    fresh_input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int


class PricingService:
    """Integer nano-USD pricing. Reasoning uses the output rate exactly once."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def validate(self, usage: TokenUsage) -> None:
        for name, value in (
            ("fresh_input_tokens", usage.fresh_input_tokens),
            ("cached_input_tokens", usage.cached_input_tokens),
            ("output_tokens", usage.output_tokens),
            ("reasoning_tokens", usage.reasoning_tokens),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValidationAppError(
                    f"{name} must be a non-negative integer.",
                    {"field": name, "value": value},
                )

    def quote(self, usage: TokenUsage) -> int:
        self.validate(usage)
        return (
            usage.fresh_input_tokens * self.settings.input_rate_nano_usd
            + usage.cached_input_tokens * self.settings.cached_input_rate_nano_usd
            + (usage.output_tokens + usage.reasoning_tokens) * self.settings.output_rate_nano_usd
        )

    @property
    def version(self) -> str:
        return self.settings.pricing_version
