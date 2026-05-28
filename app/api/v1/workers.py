"""QStash 콜백 워커 엔드포인트.

QStash가 호출하는 내부 엔드포인트. 서명 검증 후 실제 작업을 수행한다.
외부 직접 호출 방지를 위해 QStash 서명 검증을 거친다.
"""

import hashlib
import logging
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security_utils import is_ssrf_safe_url
from app.core.dependencies import (
    get_analysis_service,
    get_c2pa_service,
    get_evidence_capture_service,
    get_file_storage_service,
    get_qstash_service,
    get_redis_service,
    get_stegai_service,
)
from app.models.case import EvidenceFile, InfringementCase
from app.models.detection import DetectedMatch, DetectionRequest
from app.models.image import C2paManifest, OriginalImage, ProtectedImage
from app.models.organization import Organization
from app.models.project import Project
from app.schemas.c2pa import C2paMetadata
from app.services.analysis_service import AnalysisService
from app.services.c2pa_service import C2paService
from app.services.evidence_capture_service import EvidenceCaptureService
from app.services.evidence_integrity_service import EvidenceIntegrityService
from app.services.file_storage_service import FileStorageService
from app.services.qstash_service import QStashService
from app.services.redis_service import RedisService
from app.services.stegai_service import StegAIService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workers", tags=["workers"])

integrity_svc = EvidenceIntegrityService()


async def _verify_qstash(request: Request, qstash_svc: QStashService) -> bool:
    """QStash 서명을 검증한다."""
    signature = request.headers.get("upstash-signature", "")
    if not signature:
        # 개발 환경에서만 직접 호출 허용 (프로덕션 하드 차단)
        if (
            settings.ENVIRONMENT != "production"
            and not qstash_svc.enabled
            and settings.ALLOW_DIRECT_WORKER_CALLS
        ):
            logger.warning("Direct worker call allowed (dev mode only)")
            return True
        return False

    body = (await request.body()).decode("utf-8")
    url = str(request.url)
    return qstash_svc.verify_signature(signature=signature, body=body, url=url)


def _validate_capture_url(url: str) -> bool:
    """캡처 URL의 SSRF 방지 검증 (DNS 리졸브 후 내부 IP 차단)."""
    return is_ssrf_safe_url(url)


def _sanitize_filename(name: str) -> str:
    """파일명에서 위험 문자 제거."""
    return re.sub(r"[^a-zA-Z0-9가-힣_\-.]", "_", name[:100])


# ── 이미지 보호 워커 ────────────────────────────

@router.post("/protect-image")
async def worker_protect_image(
    request: Request,
    db: AsyncSession = Depends(get_db),
    qstash_svc: QStashService = Depends(get_qstash_service),
    redis_svc: RedisService = Depends(get_redis_service),
    stegai: StegAIService = Depends(get_stegai_service),
    c2pa_svc: C2paService = Depends(get_c2pa_service),
    file_storage: FileStorageService = Depends(get_file_storage_service),
):
    """이미지 보호 처리 워커: 워터마크 삽입 + C2PA manifest 생성."""
    if not await _verify_qstash(request, qstash_svc):
        return JSONResponse(status_code=401, content={"detail": "Invalid signature"})

    data = await request.json()
    job_id = data["job_id"]
    image_id: uuid.UUID = uuid.UUID(data["image_id"])
    user_id: uuid.UUID = uuid.UUID(data["user_id"])

    await redis_svc.update_job(job_id, status="processing", step="loading", progress=10)

    try:
        # 이미지 조회 (소유권 검증 포함)
        result = await db.execute(
            select(OriginalImage)
            .join(Project, OriginalImage.project_id == Project.id)
            .join(Organization, Project.organization_id == Organization.id)
            .where(
                OriginalImage.id == image_id,
                Organization.owner_id == user_id,
            )
        )
        image = result.scalar_one_or_none()
        if not image:
            await redis_svc.fail_job(job_id, "Image not found")
            return JSONResponse(status_code=200, content={"status": "failed"})

        # 이미 보호 확인
        existing = await db.execute(
            select(ProtectedImage).where(ProtectedImage.original_image_id == image.id)
        )
        if existing.scalar_one_or_none():
            await redis_svc.fail_job(job_id, "Image already protected")
            return JSONResponse(status_code=200, content={"status": "skipped"})

        # MongoDB에서 원본 이미지 바이트 조회
        original_bytes = await file_storage.get(image.file_storage_key) or b""
        filename = image.original_filename or "image.jpg"
        mime_type = image.mime_type or "image/jpeg"

        # [1] Steg.AI 워터마크 삽입
        await redis_svc.update_job(job_id, step="watermark", progress=30)
        embed_result = await stegai.embed_watermark(
            image_bytes=original_bytes,
            payload=image.image_id,
            filename=filename,
        )

        if embed_result:
            current_bytes = embed_result.watermarked_image_bytes
            watermark_id = embed_result.watermark_id
            raw_response = embed_result.raw_response
        else:
            current_bytes = original_bytes
            watermark_id = None
            raw_response = None

        # [2] C2PA manifest 생성
        await redis_svc.update_job(job_id, step="c2pa", progress=60)
        c2pa_manifest_record: C2paManifest | None = None

        c2pa_metadata = C2paMetadata(
            asset_id=image.image_id,
            original_hash=image.sha256_hash,
            registered_at=image.registered_at,
            owner_reference=str(user_id),
            watermark_id=watermark_id,
        )

        signed_bytes = await c2pa_svc.create_manifest(
            image_bytes=current_bytes,
            mime_type=mime_type,
            metadata=c2pa_metadata,
        )

        if signed_bytes:
            current_bytes = signed_bytes
            c2pa_manifest_record = C2paManifest(
                original_image_id=image.id,
                asset_id=image.image_id,
                original_hash=image.sha256_hash,
                registered_at=image.registered_at,
                owner_reference=user_id,
                watermark_id=watermark_id,
                manifest_data=c2pa_metadata.model_dump(mode="json"),
            )
            db.add(c2pa_manifest_record)
            await db.flush()

        # [3] ProtectedImage 저장
        await redis_svc.update_job(job_id, step="saving", progress=80)
        sha256 = hashlib.sha256(current_bytes).hexdigest() if current_bytes else image.sha256_hash
        storage_key = f"protected/{image.image_id}"

        if current_bytes:
            await file_storage.store(
                storage_key, current_bytes,
                content_type=mime_type,
                metadata={"image_id": image.image_id, "sha256": sha256},
            )

        protected = ProtectedImage(
            original_image_id=image.id,
            file_storage_key=storage_key,
            stegai_watermark_id=watermark_id,
            stegai_response=raw_response,
            c2pa_manifest_id=c2pa_manifest_record.id if c2pa_manifest_record else None,
            sha256_hash=sha256,
        )
        db.add(protected)
        image.status = "protected"

        await db.flush()
        await redis_svc.complete_job(job_id, result={
            "protected_image_id": str(protected.id),
            "watermark_id": watermark_id or "",
        })

        logger.info("Worker protect-image completed: image=%s, job=%s", image.image_id, job_id)
        return JSONResponse(status_code=200, content={"status": "completed"})

    except Exception:
        logger.exception("Worker protect-image failed: job=%s", job_id)
        await redis_svc.fail_job(job_id, "Internal processing error")
        return JSONResponse(status_code=200, content={"status": "failed"})


# ── 도용 분석 워커 ──────────────────────────────

@router.post("/analyze-image")
async def worker_analyze_image(
    request: Request,
    db: AsyncSession = Depends(get_db),
    qstash_svc: QStashService = Depends(get_qstash_service),
    redis_svc: RedisService = Depends(get_redis_service),
    analysis_svc: AnalysisService = Depends(get_analysis_service),
    file_storage: FileStorageService = Depends(get_file_storage_service),
):
    """도용 분석 워커: pHash + CLIP/DINO + ORB 파이프라인."""
    if not await _verify_qstash(request, qstash_svc):
        return JSONResponse(status_code=401, content={"detail": "Invalid signature"})

    data = await request.json()
    job_id = data["job_id"]
    request_id: uuid.UUID = uuid.UUID(data["request_id"])

    await redis_svc.update_job(job_id, status="processing", step="analyzing", progress=20)

    try:
        # DetectionRequest 조회 (소유권 교차 검증)
        expected_org_id = data.get("organization_id", "")
        result = await db.execute(
            select(DetectionRequest)
            .join(Organization, DetectionRequest.organization_id == Organization.id)
            .where(DetectionRequest.id == request_id)
        )
        det_request = result.scalar_one_or_none()
        if not det_request:
            await redis_svc.fail_job(job_id, "Detection request not found")
            return JSONResponse(status_code=200, content={"status": "failed"})

        # 메시지의 organization_id와 DB 레코드 일치 검증
        if expected_org_id and str(det_request.organization_id) != expected_org_id:
            await redis_svc.fail_job(job_id, "Organization mismatch")
            return JSONResponse(status_code=200, content={"status": "failed"})

        det_request.status = "processing"
        organization_id = str(det_request.organization_id)

        # MongoDB에서 suspect 이미지 바이트 로드
        suspect_bytes = b""
        if det_request.suspect_file_storage_key:
            suspect_bytes = await file_storage.get(det_request.suspect_file_storage_key) or b""

        await redis_svc.update_job(job_id, step="pipeline", progress=50)

        analysis_result = await analysis_svc.analyze_suspect(
            suspect_bytes=suspect_bytes,
            organization_id=organization_id,
            db=db,
        )

        # DetectedMatch 레코드 생성
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

        await db.flush()
        await redis_svc.complete_job(job_id, result={
            "total_candidates": str(len(analysis_result.candidates)),
            "best_score": str(analysis_result.best_score),
        })

        logger.info("Worker analyze-image completed: request=%s, job=%s", request_id, job_id)
        return JSONResponse(status_code=200, content={"status": "completed"})

    except Exception:
        logger.exception("Worker analyze-image failed: job=%s", job_id)
        try:
            result = await db.execute(
                select(DetectionRequest).where(DetectionRequest.id == request_id)
            )
            det_request = result.scalar_one_or_none()
            if det_request:
                det_request.status = "failed"
                det_request.completed_at = datetime.now(timezone.utc)
        except Exception:
            pass
        await redis_svc.fail_job(job_id, "Internal processing error")
        return JSONResponse(status_code=200, content={"status": "failed"})


# ── 증거 캡처 워커 ──────────────────────────────

@router.post("/capture-evidence")
async def worker_capture_evidence(
    request: Request,
    db: AsyncSession = Depends(get_db),
    qstash_svc: QStashService = Depends(get_qstash_service),
    redis_svc: RedisService = Depends(get_redis_service),
    capture_svc: EvidenceCaptureService = Depends(get_evidence_capture_service),
    file_storage: FileStorageService = Depends(get_file_storage_service),
):
    """증거 캡처 워커: 웹 페이지 스크린샷 + 이미지 다운로드 + Merkle root."""
    if not await _verify_qstash(request, qstash_svc):
        return JSONResponse(status_code=401, content={"detail": "Invalid signature"})

    data = await request.json()
    job_id = data["job_id"]
    case_id: uuid.UUID = uuid.UUID(data["case_id"])
    url: str = data["url"]

    # SSRF 방지: 내부 네트워크 URL 차단
    if not _validate_capture_url(url):
        await redis_svc.fail_job(job_id, "Invalid or blocked URL")
        return JSONResponse(status_code=200, content={"status": "failed"})

    await redis_svc.update_job(job_id, status="processing", step="capturing", progress=10)

    try:
        # Case 조회
        result = await db.execute(
            select(InfringementCase).where(InfringementCase.id == case_id)
        )
        case = result.scalar_one_or_none()
        if not case:
            await redis_svc.fail_job(job_id, "Case not found")
            return JSONResponse(status_code=200, content={"status": "failed"})

        if not capture_svc.enabled:
            await redis_svc.fail_job(job_id, "Playwright not available")
            return JSONResponse(status_code=200, content={"status": "failed"})

        # [1] 페이지 캡처
        await redis_svc.update_job(job_id, step="page_capture", progress=20)
        capture_result = await capture_svc.capture_page(url)
        if not capture_result:
            await redis_svc.fail_job(job_id, f"Failed to capture: {url}")
            return JSONResponse(status_code=200, content={"status": "failed"})

        now = datetime.now(timezone.utc)
        all_hashes: list[str] = []
        evidence_records: list[EvidenceFile] = []

        # [2] 스크린샷 증거
        await redis_svc.update_job(job_id, step="screenshot", progress=40)
        screenshot_hash = integrity_svc.hash_bytes(capture_result.screenshot_bytes)
        all_hashes.append(screenshot_hash)

        screenshot_ef = EvidenceFile(
            infringement_case_id=case.id,
            file_type="webpage_screenshot",
            file_storage_key=f"evidence/{case.id}/screenshot/{screenshot_hash[:8]}.png",
            file_name=f"screenshot_{_sanitize_filename(capture_result.page_title)}.png",
            sha256_hash=screenshot_hash,
            captured_at=now,
            metadata_={
                "url": url,
                "final_url": capture_result.final_url,
                "page_title": capture_result.page_title,
                "size_bytes": len(capture_result.screenshot_bytes),
            },
        )
        await file_storage.store(
            screenshot_ef.file_storage_key, capture_result.screenshot_bytes,
            content_type="image/png",
        )
        db.add(screenshot_ef)
        evidence_records.append(screenshot_ef)

        # [3] HTML 스냅샷 증거
        html_bytes = capture_result.html_content.encode("utf-8")
        html_hash = integrity_svc.hash_bytes(html_bytes)
        all_hashes.append(html_hash)

        html_ef = EvidenceFile(
            infringement_case_id=case.id,
            file_type="html_snapshot",
            file_storage_key=f"evidence/{case.id}/html/{html_hash[:8]}.html",
            file_name=f"snapshot_{_sanitize_filename(capture_result.page_title)}.html",
            sha256_hash=html_hash,
            captured_at=now,
            metadata_={
                "url": url,
                "final_url": capture_result.final_url,
                "page_title": capture_result.page_title,
                "size_bytes": len(html_bytes),
            },
        )
        await file_storage.store(
            html_ef.file_storage_key, html_bytes,
            content_type="text/html",
        )
        db.add(html_ef)
        evidence_records.append(html_ef)

        # [4] 이미지 다운로드
        await redis_svc.update_job(job_id, step="downloading_images", progress=60)
        downloaded = await capture_svc.download_images(capture_result.image_urls)

        _SAFE_EXTENSIONS = {"jpeg": "jpg", "jpg": "jpg", "png": "png", "webp": "webp", "gif": "gif"}

        for img in downloaded:
            all_hashes.append(img.sha256_hash)
            filename = img.url.split("/")[-1].split("?")[0][:100] or "image"
            raw_ext = img.mime_type.split("/")[-1].lower().split("+")[0]
            ext = _SAFE_EXTENSIONS.get(raw_ext, "bin")

            img_ef = EvidenceFile(
                infringement_case_id=case.id,
                file_type="suspect_image",
                file_storage_key=f"evidence/{case.id}/images/{img.sha256_hash[:8]}.{ext}",
                file_name=filename,
                sha256_hash=img.sha256_hash,
                captured_at=now,
                metadata_={
                    "source_url": img.url,
                    "mime_type": img.mime_type,
                    "size_bytes": len(img.image_bytes),
                },
            )
            await file_storage.store(
                img_ef.file_storage_key, img.image_bytes,
                content_type=img.mime_type,
            )
            db.add(img_ef)
            evidence_records.append(img_ef)

        # [5] Merkle root
        await redis_svc.update_job(job_id, step="merkle_root", progress=90)
        chain = integrity_svc.create_evidence_chain(all_hashes)

        if not case.suspect_url:
            case.suspect_url = url

        await db.flush()

        await redis_svc.complete_job(job_id, result={
            "evidence_count": str(len(evidence_records)),
            "images_found": str(len(capture_result.image_urls)),
            "images_downloaded": str(len(downloaded)),
            "merkle_root": chain["merkle_root"],
        })

        logger.info(
            "Worker capture-evidence completed: case=%s, %d files, job=%s",
            case.case_number, len(evidence_records), job_id,
        )
        return JSONResponse(status_code=200, content={"status": "completed"})

    except Exception:
        logger.exception("Worker capture-evidence failed: job=%s", job_id)
        await redis_svc.fail_job(job_id, "Internal processing error")
        return JSONResponse(status_code=200, content={"status": "failed"})
