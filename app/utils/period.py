from datetime import UTC, datetime

from app.db.models.subscription import Subscription


def utc_month_bounds(moment: datetime | None = None) -> tuple[datetime, datetime]:
    now = (moment or datetime.now(UTC)).astimezone(UTC)
    start = datetime(now.year, now.month, 1, tzinfo=UTC)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    return start, end


def billing_period(subscription: Subscription | None, moment: datetime | None = None) -> tuple[datetime, datetime]:
    """Stripe period when both ends are set; otherwise UTC calendar month."""
    if (
        subscription is not None
        and subscription.current_period_start is not None
        and subscription.current_period_end is not None
    ):
        start = subscription.current_period_start
        end = subscription.current_period_end
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        return start, end
    return utc_month_bounds(moment)


def seconds_until(moment: datetime) -> int:
    delta = moment - datetime.now(UTC)
    return max(int(delta.total_seconds()), 1)
