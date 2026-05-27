import uuid
from datetime import datetime

from pydantic import BaseModel


class DetectionByUrlRequest(BaseModel):
    suspect_url: str


class DetectionByImageRequest(BaseModel):
    pass  # 파일은 Form/UploadFile로 수신


class DetectionResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    request_type: str
    suspect_url: str | None
    status: str
    result_summary: dict | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class MatchResponse(BaseModel):
    id: uuid.UUID
    detection_request_id: uuid.UUID
    original_image_id: uuid.UUID | None
    watermark_detected: bool
    similarity_phash: float | None
    similarity_clip: float | None
    similarity_dino: float | None
    overall_score: float | None
    transformation_types: list[str] | None
    risk_level: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
