import pytest
from app.core.exceptions import ValidationAppError
from app.services.pricing_service import PricingService, TokenUsage

# Manual expected totals using demo rates:
# fresh 3000 nano/token, cached 300, output/reasoning 15000.


def quote(**kwargs) -> int:
    return PricingService().quote(TokenUsage(**kwargs))


def test_input_tokens_only() -> None:
    assert quote(
        fresh_input_tokens=10,
        cached_input_tokens=0,
        output_tokens=0,
        reasoning_tokens=0,
    ) == 10 * 3000


def test_cached_input_tokens_only() -> None:
    assert quote(
        fresh_input_tokens=0,
        cached_input_tokens=10,
        output_tokens=0,
        reasoning_tokens=0,
    ) == 10 * 300


def test_output_tokens_only() -> None:
    assert quote(
        fresh_input_tokens=0,
        cached_input_tokens=0,
        output_tokens=10,
        reasoning_tokens=0,
    ) == 10 * 15000


def test_reasoning_tokens_only_use_output_rate_once() -> None:
    assert quote(
        fresh_input_tokens=0,
        cached_input_tokens=0,
        output_tokens=0,
        reasoning_tokens=10,
    ) == 10 * 15000


def test_mixed_request_manual_total() -> None:
    # 120*3000 + 20*300 + (80+15)*15000 = 360000 + 6000 + 1425000 = 1791000
    assert quote(
        fresh_input_tokens=120,
        cached_input_tokens=20,
        output_tokens=80,
        reasoning_tokens=15,
    ) == 1_791_000


def test_zero_tokens() -> None:
    assert quote(
        fresh_input_tokens=0,
        cached_input_tokens=0,
        output_tokens=0,
        reasoning_tokens=0,
    ) == 0


@pytest.mark.parametrize("field", ["fresh_input_tokens", "cached_input_tokens", "output_tokens", "reasoning_tokens"])
def test_negative_rejected(field: str) -> None:
    kwargs = {
        "fresh_input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        field: -1,
    }
    with pytest.raises(ValidationAppError):
        quote(**kwargs)


def test_large_quantities() -> None:
    amount = quote(
        fresh_input_tokens=1_000_000,
        cached_input_tokens=0,
        output_tokens=0,
        reasoning_tokens=0,
    )
    assert amount == 1_000_000 * 3000
    assert isinstance(amount, int)
