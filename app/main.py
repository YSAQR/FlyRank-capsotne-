from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes.billing import router as billing_router
from app.api.routes.health import router as health_router
from app.api.routes.tenants import router as tenants_router
from app.api.routes.usage import router as usage_router
from app.api.routes.webhooks import router as webhooks_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="FlyRank Usage Metering & Billing Engine",
    version="0.1.0",
    description=(
        "Demo billing core for Free/Pro plans. Tenant identity uses development headers "
        "X-Dev-Token and X-Tenant-Id — not production authentication. Stripe is TEST mode only."
    ),
)

app.include_router(health_router)
app.include_router(tenants_router)
app.include_router(usage_router)
app.include_router(billing_router)
app.include_router(webhooks_router)


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message, "details": exc.details},
        headers=exc.headers or None,
    )


@app.exception_handler(RequestValidationError)
async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed.",
            "details": {"errors": exc.errors()},
        },
    )


@app.exception_handler(Exception)
async def unhandled_handler(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred.",
            "details": {},
        },
    )
