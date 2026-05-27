import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class DetectionRequest(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "detection_requests"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    request_type: Mapped[str] = mapped_column(String(20), nullable=False)
    suspect_url: Mapped[str | None] = mapped_column(Text)
    suspect_file_storage_key: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    result_summary: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    matches = relationship("DetectedMatch", back_populates="detection_request", cascade="all, delete-orphan")


class DetectedMatch(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "detected_matches"

    detection_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("detection_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_image_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("original_images.id"), index=True
    )
    suspect_image_storage_key: Mapped[str | None] = mapped_column(String(500))
    watermark_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    watermark_id: Mapped[str | None] = mapped_column(String(200))
    similarity_phash: Mapped[float | None] = mapped_column(Float)
    similarity_clip: Mapped[float | None] = mapped_column(Float)
    similarity_dino: Mapped[float | None] = mapped_column(Float)
    overall_score: Mapped[float | None] = mapped_column(Float)
    transformation_types = mapped_column(ARRAY(Text), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(10), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    detection_request = relationship("DetectionRequest", back_populates="matches")
