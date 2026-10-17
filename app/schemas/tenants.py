from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TenantRead(BaseModel):
    id: UUID
    name: str
    status: str
    created_at: datetime
    plan_code: str
    subscription_status: str
