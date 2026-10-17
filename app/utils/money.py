"""Integer monetary helpers. Application unit is nano-USD (1 USD = 1_000_000_000)."""

NANO_USD_PER_USD = 1_000_000_000


def format_nano_usd(amount: int) -> dict[str, str | int]:
    return {
        "amount": amount,
        "currency": "USD",
        "unit": "nano_usd",
        "amount_usd": _nano_to_usd_string(amount),
    }


def _nano_to_usd_string(amount: int) -> str:
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    whole, frac = divmod(amount, NANO_USD_PER_USD)
    return f"{sign}{whole}.{frac:09d}"
