from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    input_tokens: int = Field(ge=0, description="Fresh (uncached) input tokens")
    cached_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    reasoning_tokens: int = Field(ge=0)

    @model_validator(mode="after")
    def require_some_work(self) -> "GenerateRequest":
        total = (
            self.input_tokens
            + self.cached_input_tokens
            + self.output_tokens
            + self.reasoning_tokens
        )
        if total == 0:
            raise ValueError("At least one token quantity must be greater than zero.")
        return self

    def token_breakdown(self) -> dict[str, int]:
        return {
            "fresh_input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
        }

    def billable_tokens(self) -> int:
        return (
            self.input_tokens
            + self.cached_input_tokens
            + self.output_tokens
            + self.reasoning_tokens
        )


class CostBreakdown(BaseModel):
    amount: int
    currency: str
    unit: str
    amount_usd: str
    pricing_version: str


class GenerateUsage(BaseModel):
    api_calls: int
    fresh_input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    billable_tokens: int


class GenerateResponse(BaseModel):
    generation_id: UUID
    output: str
    usage: GenerateUsage
    cost: CostBreakdown
    idempotent_replay: bool
    quota: dict[str, Any]
