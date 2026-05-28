import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import BIT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class OriginalImage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "original_images"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    image_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    file_storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(500))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    mime_type: Mapped[str | None] = mapped_column(String(50))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    product_name: Mapped[str | None] = mapped_column(String(300))
    brand_name: Mapped[str | None] = mapped_column(String(200))
    shot_date: Mapped[date | None] = mapped_column(Date)
    rights_holder: Mapped[str | None] = mapped_column(String(300))
    rights_holder_info: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="registered")
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="original_images")
    protected_images = relationship("ProtectedImage", back_populates="original_image", cascade="all, delete-orphan")
    fingerprints = relationship("ImageFingerprint", back_populates="original_image", cascade="all, delete-orphan")
    c2pa_manifests = relationship("C2paManifest", back_populates="original_image", cascade="all, delete-orphan")


class ImageFingerprint(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "image_fingerprints"

    original_image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("original_images.id", ondelete="CASCADE"), nullable=False, index=True
    )
    phash: Mapped[str | None] = mapped_column(String(64), index=True)
    phash_binary = mapped_column(BIT(64), nullable=True)
    clip_vector_id: Mapped[str | None] = mapped_column(String(100))
    dino_vector_id: Mapped[str | None] = mapped_column(String(100))
    product_region_vector_id: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    original_image = relationship("OriginalImage", back_populates="fingerprints")


class C2paManifest(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "c2pa_manifests"

    original_image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("original_images.id", ondelete="CASCADE"), nullable=False
    )
    creator: Mapped[str] = mapped_column(String(100), default="Re-Proof")
    claim_generator: Mapped[str] = mapped_column(String(200), default="Re-Proof Image Protection Engine")
    asset_id: Mapped[str | None] = mapped_column(String(100))
    original_hash: Mapped[str | None] = mapped_column(String(64))
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    owner_reference: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    watermark_provider: Mapped[str] = mapped_column(String(50), default="Steg.AI")
    watermark_id: Mapped[str | None] = mapped_column(String(200))
    manifest_data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    original_image = relationship("OriginalImage", back_populates="c2pa_manifests")


class ProtectedImage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "protected_images"

    original_image_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("original_images.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    stegai_watermark_id: Mapped[str | None] = mapped_column(String(200), index=True)
    stegai_response: Mapped[dict | None] = mapped_column(JSONB)
    c2pa_manifest_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("c2pa_manifests.id")
    )
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    original_image = relationship("OriginalImage", back_populates="protected_images")
    c2pa_manifest = relationship("C2paManifest")
