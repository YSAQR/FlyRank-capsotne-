from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def with_retries[T](
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay_seconds: float = 0.5,
    operation_name: str = "job",
) -> T:
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            logger.error(
                "ALERT job_failure operation=%s attempt=%s/%s error_type=%s",
                operation_name,
                attempt,
                attempts,
                type(exc).__name__,
            )
            if attempt < attempts:
                time.sleep(base_delay_seconds * (2 ** (attempt - 1)))
    assert last_error is not None
    raise last_error
