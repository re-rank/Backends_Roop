import uuid
from datetime import datetime

from pydantic import BaseModel


# ── Steg.AI 내부 응답 모델 ──


class StegAIEmbedResult(BaseModel):
    """Steg.AI embed API 응답을 정규화한 내부 모델."""

    watermark_id: str
    payload: str
    watermarked_image_bytes: bytes
    confidence: float | None = None
    raw_response: dict | None = None


class StegAIDetectResult(BaseModel):
    """Steg.AI detect API 응답을 정규화한 내부 모델."""

    detected: bool
    watermark_id: str | None = None
    payload: str | None = None
    confidence: float | None = None
    raw_response: dict | None = None


# ── API 요청/응답 스키마 ──


class ProtectRequest(BaseModel):
    """이미지 보호 처리 요청 (현재는 별도 파라미터 없음, 확장용)."""

    pass


class ProtectResponse(BaseModel):
    """이미지 보호 처리 결과."""

    id: uuid.UUID
    original_image_id: uuid.UUID
    stegai_watermark_id: str | None
    sha256_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WatermarkDetectResponse(BaseModel):
    """워터마크 검출 결과."""

    detected: bool
    watermark_id: str | None = None
    payload: str | None = None
    confidence: float | None = None
    matched_original_image_id: uuid.UUID | None = None
