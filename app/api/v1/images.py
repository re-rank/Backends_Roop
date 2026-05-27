import hashlib
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import (
    get_analysis_service,
    get_c2pa_service,
    get_current_user,
    get_file_storage_service,
    get_qstash_service,
    get_redis_service,
    get_stegai_service,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.security_utils import read_upload_safely
from app.models.image import C2paManifest, ImageFingerprint, OriginalImage, ProtectedImage
from app.models.organization import Organization
from app.models.project import Project
from app.models.user import User
from app.schemas.c2pa import C2paMetadata
from app.schemas.common import PaginatedResponse
from app.schemas.image import ImageResponse
from app.schemas.watermark import ProtectResponse
from app.services.analysis_service import AnalysisService
from app.services.c2pa_service import C2paService
from app.services.file_storage_service import FileStorageService
from app.services.phash_service import PHashService
from app.services.qstash_service import QStashService
from app.services.redis_service import RedisService
from app.services.stegai_service import StegAIService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["images"])

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _generate_image_id() -> str:
    now = datetime.now(timezone.utc)
    seq = uuid.uuid4().hex[:6].upper()
    return f"RP-IMG-{now.strftime('%Y%m%d')}-{seq}"


async def _verify_project_access(
    project_id: uuid.UUID, db: AsyncSession, user: User
) -> Project:
    result = await db.execute(
        select(Project)
        .join(Organization, Project.organization_id == Organization.id)
        .where(Project.id == project_id, Organization.owner_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundError("Project")
    return project


async def _get_image_or_404(
    image_id: uuid.UUID, db: AsyncSession, user: User
) -> OriginalImage:
    result = await db.execute(
        select(OriginalImage)
        .join(Project, OriginalImage.project_id == Project.id)
        .join(Organization, Project.organization_id == Organization.id)
        .where(OriginalImage.id == image_id, Organization.owner_id == user.id)
    )
    image = result.scalar_one_or_none()
    if not image:
        raise NotFoundError("Image")
    return image


@router.post(
    "/projects/{project_id}/images",
    response_model=ImageResponse,
    status_code=201,
)
async def upload_image(
    project_id: uuid.UUID,
    file: UploadFile,
    product_name: str | None = None,
    brand_name: str | None = None,
    rights_holder: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analysis_svc: AnalysisService = Depends(get_analysis_service),
    file_storage: FileStorageService = Depends(get_file_storage_service),
):
    project = await _verify_project_access(project_id, db, current_user)

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise BadRequestError(f"Unsupported file type: {file.content_type}. Allowed: JPEG, PNG, WebP")

    content = await read_upload_safely(file)
    sha256 = hashlib.sha256(content).hexdigest()

    image_id = _generate_image_id()
    storage_key = f"originals/{image_id}"

    await file_storage.store(
        storage_key,
        content,
        content_type=file.content_type,
        metadata={"image_id": image_id, "sha256": sha256},
    )

    image = OriginalImage(
        project_id=project_id,
        image_id=image_id,
        file_storage_key=storage_key,
        original_filename=file.filename,
        file_size_bytes=len(content),
        mime_type=file.content_type,
        sha256_hash=sha256,
        product_name=product_name,
        brand_name=brand_name,
        rights_holder=rights_holder,
    )
    db.add(image)
    await db.flush()
    await db.refresh(image)

    # ── 지문 생성 (pHash + CLIP/DINO 임베딩) ──
    fp_result = await analysis_svc.generate_fingerprint(
        image_bytes=content,
        original_image_id=image.id,
        organization_id=str(project.organization_id),
        image_id=image.image_id,
    )

    fingerprint = ImageFingerprint(
        original_image_id=image.id,
        phash=fp_result.phash_hex,
        phash_binary=PHashService.phash_hex_to_bits(fp_result.phash_hex) if fp_result.phash_hex else None,
        clip_vector_id=str(image.id) if fp_result.clip_vector else None,
        dino_vector_id=str(image.id) if fp_result.dino_vector else None,
    )
    db.add(fingerprint)

    return ImageResponse.model_validate(image)


@router.get(
    "/projects/{project_id}/images",
    response_model=PaginatedResponse[ImageResponse],
)
async def list_images(
    project_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_project_access(project_id, db, current_user)

    base_query = select(OriginalImage).where(OriginalImage.project_id == project_id)
    if status:
        base_query = base_query.where(OriginalImage.status == status)

    total_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(
        base_query.order_by(OriginalImage.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    images = result.scalars().all()

    return PaginatedResponse.create(
        items=[ImageResponse.model_validate(img) for img in images],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/images/{image_id}", response_model=ImageResponse)
async def get_image(
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image = await _get_image_or_404(image_id, db, current_user)
    return ImageResponse.model_validate(image)


@router.delete("/images/{image_id}", status_code=204)
async def delete_image(
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    file_storage: FileStorageService = Depends(get_file_storage_service),
):
    image = await _get_image_or_404(image_id, db, current_user)
    storage_key = image.file_storage_key
    await db.delete(image)
    await db.flush()
    # GridFS는 DB 삭제 확정 후 삭제 (실패해도 고아 파일만 남음)
    await file_storage.delete(storage_key)


@router.post(
    "/images/{image_id}/protect",
    status_code=202,
)
async def protect_image(
    image_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    stegai: StegAIService = Depends(get_stegai_service),
    c2pa_svc: C2paService = Depends(get_c2pa_service),
    qstash_svc: QStashService = Depends(get_qstash_service),
    redis_svc: RedisService = Depends(get_redis_service),
    file_storage: FileStorageService = Depends(get_file_storage_service),
):
    """이미지 보호 처리 파이프라인.

    QStash 설정 시: 작업을 큐에 발행하고 job_id를 반환 (202 Accepted)
    QStash 미설정 시: 동기 처리 후 결과를 반환 (fallback)
    """
    image = await _get_image_or_404(image_id, db, current_user)

    # 이미 보호된 이미지인지 확인
    existing = await db.execute(
        select(ProtectedImage).where(ProtectedImage.original_image_id == image.id)
    )
    if existing.scalar_one_or_none():
        raise BadRequestError("Image is already protected")

    # ── QStash 비동기 처리 ──
    if qstash_svc.enabled:
        job_id = uuid.uuid4().hex
        await redis_svc.create_job(job_id, "protect-image", metadata={
            "image_id": str(image.id),
            "image_code": image.image_id,
            "owner_id": str(current_user.id),
        })
        await qstash_svc.publish(
            "/api/v1/workers/protect-image",
            body={
                "job_id": job_id,
                "image_id": str(image.id),
                "user_id": str(current_user.id),
            },
        )
        image.status = "processing"
        return {"job_id": job_id, "status": "queued", "message": "Protection job queued"}

    # ── Fallback: 동기 처리 ──
    original_bytes = await file_storage.get(image.file_storage_key) or b""
    filename = image.original_filename or "image.jpg"
    mime_type = image.mime_type or "image/jpeg"

    embed_result = await stegai.embed_watermark(
        image_bytes=original_bytes, payload=image.image_id, filename=filename,
    )

    if embed_result:
        current_bytes = embed_result.watermarked_image_bytes
        watermark_id = embed_result.watermark_id
        raw_response = embed_result.raw_response
    else:
        current_bytes = original_bytes
        watermark_id = None
        raw_response = None

    c2pa_manifest_record: C2paManifest | None = None
    c2pa_metadata = C2paMetadata(
        asset_id=image.image_id,
        original_hash=image.sha256_hash,
        registered_at=image.registered_at,
        owner_reference=str(current_user.id),
        watermark_id=watermark_id,
    )
    signed_bytes = await c2pa_svc.create_manifest(
        image_bytes=current_bytes, mime_type=mime_type, metadata=c2pa_metadata,
    )
    if signed_bytes:
        current_bytes = signed_bytes
        c2pa_manifest_record = C2paManifest(
            original_image_id=image.id, asset_id=image.image_id,
            original_hash=image.sha256_hash, registered_at=image.registered_at,
            owner_reference=current_user.id, watermark_id=watermark_id,
            manifest_data=c2pa_metadata.model_dump(mode="json"),
        )
        db.add(c2pa_manifest_record)
        await db.flush()

    sha256 = hashlib.sha256(current_bytes).hexdigest() if current_bytes else image.sha256_hash
    protected_key = f"protected/{image.image_id}"
    if current_bytes:
        await file_storage.store(
            protected_key, current_bytes,
            content_type=mime_type,
            metadata={"image_id": image.image_id, "sha256": sha256},
        )
    protected = ProtectedImage(
        original_image_id=image.id, file_storage_key=protected_key,
        stegai_watermark_id=watermark_id, stegai_response=raw_response,
        c2pa_manifest_id=c2pa_manifest_record.id if c2pa_manifest_record else None,
        sha256_hash=sha256,
    )
    db.add(protected)
    image.status = "protected"

    await db.flush()
    await db.refresh(protected)
    return ProtectResponse.model_validate(protected)
