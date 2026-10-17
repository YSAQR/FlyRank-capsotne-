import pytest
from app.jobs.retry_utils import with_retries


def test_retries_then_succeeds() -> None:
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("nope")
        return "ok"

    assert with_retries(flaky, attempts=3, base_delay_seconds=0.01) == "ok"
    assert calls["n"] == 3


def test_retries_exhausted() -> None:
    def always_fail() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError):
        with_retries(always_fail, attempts=2, base_delay_seconds=0.01)
