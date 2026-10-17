from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_tenant
from app.core.exceptions import ValidationAppError
from app.db.models.tenant import Tenant
from app.db.session import get_db
from app.schemas.billing import CheckoutResponse
from app.schemas.generate import GenerateRequest, GenerateResponse
from app.services.stripe_service import StripeService
from app.services.usage_service import UsageService

router = APIRouter(tags=["billing"])


@router.post("/generate", response_model=GenerateResponse)
def generate(
    payload: GenerateRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> GenerateResponse:
    if not idempotency_key:
        raise ValidationAppError("Idempotency-Key header is required.")
    return UsageService(db).generate(tenant.id, idempotency_key, payload)


@router.post("/billing/checkout", response_model=CheckoutResponse)
def checkout(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    result = StripeService(db).create_checkout_session(tenant.id)
    return CheckoutResponse.model_validate(result)
