from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_dev_token
from app.db.session import get_db
from app.schemas.tenants import TenantCreate, TenantRead
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreate,
    _: None = Depends(require_dev_token),
    db: Session = Depends(get_db),
) -> TenantRead:
    return SubscriptionService(db).create_tenant(payload)
