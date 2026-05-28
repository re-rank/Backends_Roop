import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
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
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.core.security_utils import read_upload_safely
from app.models.detection import DetectedMatch, DetectionRequest
from app.models.image import C2paManifest, ProtectedImage
from app.models.organization import Organization
from app.models.user import User
from app.schemas.c2pa import C2paVerifyResult
from app.schemas.detection import DetectionByUrlRequest, DetectionResponse, MatchResponse
from app.schemas.watermark import WatermarkDetectResponse
from app.services.analysis_service import AnalysisService
from app.services.c2pa_service import C2paService
from app.services.file_storage_service import FileStorageService
from app.services.qstash_service import QStashService
from app.services.redis_service import RedisService
from app.services.stegai_service import StegAIService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/detection", tags=["detection"])

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


async def _verify_org_access(
    organization_id: uuid.UUID, db: AsyncSession, user: User
) -> None:
    """현재 사용자가 해당 조직의 소유자인지 검증."""
    result = await db.execute(
        select(Organization).where(
            Organization.id == organization_id,
            Organization.owner_id == user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise ForbiddenError("No access to this organization")


@router.post("/analyze-url", response_model=DetectionResponse, status_code=201)
async def analyze_url(
    body: DetectionByUrlRequest,
    organization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    qstash_svc: QStashService = Depends(get_qstash_service),
    redis_svc: RedisService = Depends(get_redis_service),
):
    await _verify_org_access(organization_id, db, current_user)

    det_request = DetectionRequest(
        organization_id=organization_id,
        request_type="url",
        suspect_url=body.suspect_url,
        status="pending",
    )
    db.add(det_request)
    await db.flush()
    await db.refresh(det_request)

    # QStash로 비동기 분석 발행
    if qstash_svc.enabled:
        job_id = uuid.uuid4().hex
        await redis_svc.create_job(job_id, "analyze-url", metadata={
            "request_id": str(det_request.id),
            "url": body.suspect_url,
            "owner_id": str(current_user.id),
        })
        await qstash_svc.publish(
            "/api/v1/workers/analyze-image",
            body={
                "job_id": job_id,
                "request_id": str(det_request.id),
                "organization_id": str(organization_id),
            },
        )
        det_request.status = "queued"
        det_request.result_summary = {"job_id": job_id}

    return DetectionResponse.model_validate(det_request)


@router.post("/analyze-image", response_model=DetectionResponse, status_code=201)
async def analyze_image(
    file: UploadFile,
    organization_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    analysis_svc: AnalysisService = Depends(get_analysis_service),
    qstash_svc: QStashService = Depends(get_qstash_service),
    redis_svc: RedisService = Depends(get_redis_service),
    file_storage: FileStorageService = Depends(get_file_storage_service),
):
    await _verify_org_access(organization_id, db, current_user)

    if file.content_type not in ALLOWED_MIME_TYPES:
        raise BadRequestError(f"Unsupported file type: {file.content_type}")

    content = await read_upload_safely(file)

    suspect_key = f"suspects/{uuid.uuid4().hex}"
    await file_storage.store(
        suspect_key, content,
        content_type=file.content_type,
        metadata={"organization_id": str(organization_id)},
    )

    det_request = DetectionRequest(
        organization_id=organization_id,
        request_type="upload",
        suspect_file_storage_key=suspect_key,
        status="pending",
    )
    db.add(det_request)
    await db.flush()
    await db.refresh(det_request)

    # ── QStash 비동기 처리 ──
    if qstash_svc.enabled:
        job_id = uuid.uuid4().hex
        await redis_svc.create_job(job_id, "analyze-image", metadata={
            "request_id": str(det_request.id),
            "owner_id": str(current_user.id),
        })
        await qstash_svc.publish(
            "/api/v1/workers/analyze-image",
            body={
                "job_id": job_id,
                "request_id": str(det_request.id),
                "organization_id": str(organization_id),
            },
        )
        det_request.status = "queued"
        det_request.result_summary = {"job_id": job_id}
        return DetectionResponse.model_validate(det_request)

    # ── Fallback: 동기 분석 파이프라인 실행 ──
    det_request.status = "processing"
    try:
        analysis_result = await analysis_svc.analyze_suspect(
            suspect_bytes=content,
            organization_id=str(organization_id),
            db=db,
        )

        for candidate in analysis_result.candidates:
            match = DetectedMatch(
                detection_request_id=det_request.id,
                original_image_id=candidate.original_image_id,
                similarity_phash=candidate.similarity_phash,
                similarity_clip=candidate.similarity_clip,
                similarity_dino=candidate.similarity_dino,
                overall_score=candidate.overall_score,
                risk_level=candidate.risk_level,
            )
            db.add(match)

        det_request.status = "completed"
        det_request.completed_at = datetime.now(timezone.utc)
        det_request.result_summary = {
            "total_candidates": len(analysis_result.candidates),
            "best_score": analysis_result.best_score,
            "best_risk_level": analysis_result.best_risk_level,
        }
    except Exception:
        logger.exception("Analysis pipeline failed for request %s", det_request.id)
        det_request.status = "failed"
        det_request.completed_at = datetime.now(timezone.utc)

    return DetectionResponse.model_validate(det_request)


@router.get("/{request_id}", response_model=DetectionResponse)
async def get_detection(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(DetectionRequest)
        .join(Organization, DetectionRequest.organization_id == Organization.id)
        .where(
            DetectionRequest.id == request_id,
            Organization.owner_id == current_user.id,
        )
    )
    req = result.scalar_one_or_none()
    if not req:
        raise NotFoundError("Detection request")
    return DetectionResponse.model_validate(req)


@router.get("/{request_id}/matches", response_model=list[MatchResponse])
async def get_matches(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 소유권 검증: request가 현재 사용자의 조직에 속하는지 확인
    req_result = await db.execute(
        select(DetectionRequest)
        .join(Organization, DetectionRequest.organization_id == Organization.id)
        .where(
            DetectionRequest.id == request_id,
            Organization.owner_id == current_user.id,
        )
    )
    if not req_result.scalar_one_or_none():
        raise NotFoundError("Detection request")

    result = await db.execute(
        select(DetectedMatch).where(DetectedMatch.detection_request_id == request_id)
    )
    matches = result.scalars().all()
    return [MatchResponse.model_validate(m) for m in matches]


@router.post("/detect-watermark", response_model=WatermarkDetectResponse)
async def detect_watermark(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    stegai: StegAIService = Depends(get_stegai_service),
):
    """
    의심 이미지에서 워터마크를 검출한다.

    워터마크가 발견되면 원본 이미지를 즉시 매칭하고,
    미발견 시 유사도 분석 파이프라인으로 전달해야 함을 안내한다.
    """
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise BadRequestError(f"Unsupported file type: {file.content_type}")

    content = await read_upload_safely(file)
    filename = file.filename or "suspect.jpg"

    result = await stegai.detect_watermark(content, filename)

    matched_original_id: uuid.UUID | None = None
    if result.detected and result.watermark_id:
        # watermark_id로 보호된 이미지 → 원본 이미지 역추적
        row = await db.execute(
            select(ProtectedImage).where(
                ProtectedImage.stegai_watermark_id == result.watermark_id
            )
        )
        protected = row.scalar_one_or_none()
        if protected:
            matched_original_id = protected.original_image_id
            logger.info(
                "Watermark detected: watermark_id=%s → original_image_id=%s",
                result.watermark_id,
                matched_original_id,
            )

    return WatermarkDetectResponse(
        detected=result.detected,
        watermark_id=result.watermark_id,
        payload=result.payload,
        confidence=result.confidence,
        matched_original_image_id=matched_original_id,
    )


@router.post("/verify-c2pa", response_model=C2paVerifyResult)
async def verify_c2pa(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    c2pa_svc: C2paService = Depends(get_c2pa_service),
):
    """
    의심 이미지에서 C2PA manifest를 읽고 검증한다.

    - Re-Proof manifest가 있으면 asset_id로 원본 직접 조회 가능
    - 다른 서비스의 manifest면 참고 정보로 반환
    - manifest 없으면 정상 (제거되었거나 원래 없음)
    """
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise BadRequestError(f"Unsupported file type: {file.content_type}")

    content = await read_upload_safely(file)
    mime_type = file.content_type or "image/jpeg"

    result = await c2pa_svc.read_manifest(content, mime_type)

    # Re-Proof manifest인 경우 asset_id로 원본 확인 시도
    if result.has_manifest and result.creator == "Re-Proof" and result.asset_id:
        row = await db.execute(
            select(C2paManifest).where(C2paManifest.asset_id == result.asset_id)
        )
        manifest_record = row.scalar_one_or_none()
        if manifest_record:
            logger.info(
                "C2PA Re-Proof manifest found: asset_id=%s → original_image_id=%s",
                result.asset_id,
                manifest_record.original_image_id,
            )

    return result
