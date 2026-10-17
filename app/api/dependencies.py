from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, NotFoundError, UnauthorizedError
from app.db.models.tenant import Tenant, TenantStatus
from app.db.session import get_db
from app.repositories.tenant_repository import TenantRepository


def settings_dep() -> Settings:
    return get_settings()


def require_dev_token(
    x_dev_token: Annotated[str | None, Header(alias="X-Dev-Token")] = None,
    settings: Settings = Depends(settings_dep),
) -> None:
    if not x_dev_token or x_dev_token != settings.tenant_dev_token:
        raise UnauthorizedError()


def get_current_tenant(
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
    _: None = Depends(require_dev_token),
    db: Session = Depends(get_db),
) -> Tenant:
    if not x_tenant_id:
        raise UnauthorizedError("X-Tenant-Id header is required.")
    try:
        tenant_uuid = UUID(x_tenant_id)
    except ValueError as exc:
        raise ForbiddenError("X-Tenant-Id must be a UUID.") from exc
    tenant = TenantRepository(db).get(tenant_uuid)
    if tenant is None:
        raise NotFoundError("Unknown tenant.")
    if tenant.status != TenantStatus.active.value:
        raise ForbiddenError("Tenant is disabled.")
    return tenant
