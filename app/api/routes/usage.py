from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_tenant
from app.db.models.tenant import Tenant
from app.db.session import get_db
from app.schemas.usage import UsageSummaryResponse
from app.services.usage_service import UsageService

router = APIRouter(tags=["usage"])


@router.get("/usage", response_model=UsageSummaryResponse)
def get_usage(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
) -> UsageSummaryResponse:
    return UsageService(db).summary(tenant.id)
