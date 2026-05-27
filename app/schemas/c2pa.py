import uuid
from datetime import datetime

from pydantic import BaseModel


class C2paMetadata(BaseModel):
    """C2PA manifest 생성에 필요한 메타데이터."""

    asset_id: str
    original_hash: str
    registered_at: datetime
    owner_reference: str
    watermark_provider: str = "Steg.AI"
    watermark_id: str | None = None


class C2paManifestResponse(BaseModel):
    """DB에 저장된 C2PA manifest 응답."""

    id: uuid.UUID
    original_image_id: uuid.UUID
    creator: str
    claim_generator: str
    asset_id: str | None
    original_hash: str | None
    watermark_id: str | None
    manifest_data: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class C2paVerifyResult(BaseModel):
    """C2PA manifest 검증 결과."""

    has_manifest: bool
    is_valid: bool = False
    creator: str | None = None
    claim_generator: str | None = None
    asset_id: str | None = None
    manifest_data: dict | None = None
    validation_errors: list[str] = []
