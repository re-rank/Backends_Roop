import uuid
from datetime import date, datetime

from pydantic import BaseModel


class ImageCreate(BaseModel):
    product_name: str | None = None
    brand_name: str | None = None
    shot_date: date | None = None
    rights_holder: str | None = None
    rights_holder_info: dict | None = None


class ImageResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    image_id: str
    original_filename: str | None
    file_size_bytes: int | None
    mime_type: str | None
    width: int | None
    height: int | None
    sha256_hash: str
    product_name: str | None
    brand_name: str | None
    shot_date: date | None
    rights_holder: str | None
    status: str
    registered_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class ProtectedImageResponse(BaseModel):
    id: uuid.UUID
    original_image_id: uuid.UUID
    stegai_watermark_id: str | None
    sha256_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}
