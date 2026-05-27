import uuid
from datetime import datetime

from pydantic import BaseModel


class OrganizationCreate(BaseModel):
    name: str
    brand_name: str | None = None
    business_number: str | None = None
    contact_email: str | None = None


class OrganizationUpdate(BaseModel):
    name: str | None = None
    brand_name: str | None = None
    business_number: str | None = None
    contact_email: str | None = None


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    brand_name: str | None
    business_number: str | None
    contact_email: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
