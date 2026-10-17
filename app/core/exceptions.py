from typing import Any


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.headers = headers or {}


class ValidationAppError(AppError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("VALIDATION_ERROR", message, 400, details)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Invalid or missing development token.") -> None:
        super().__init__("UNAUTHORIZED", message, 401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Tenant is not authorized for this resource.") -> None:
        super().__init__("FORBIDDEN", message, 403)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__("NOT_FOUND", message, 404)


class ConflictError(AppError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("IDEMPOTENCY_KEY_REUSED", message, 409, details)


class PaymentRequiredError(AppError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__("PAYMENT_REQUIRED", message, 402, details)


class QuotaExceededError(AppError):
    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        retry_after: int | None = None,
    ) -> None:
        headers = {"Retry-After": str(retry_after)} if retry_after is not None else None
        super().__init__("QUOTA_EXCEEDED", message, 429, details, headers)


class StripeNotConfiguredError(AppError):
    def __init__(self) -> None:
        super().__init__(
            "STRIPE_NOT_CONFIGURED",
            "Stripe TEST credentials are not configured. Set STRIPE_SECRET_KEY and STRIPE_PRO_PRICE_ID.",
            503,
        )
