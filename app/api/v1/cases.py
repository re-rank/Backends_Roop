import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_evidence_capture_service, get_file_storage_service
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.core.security_utils import is_ssrf_safe_url
from app.models.case import EvidenceFile, InfringementCase
from app.models.organization import Organization
from app.models.user import User
from app.schemas.case import (
    CaseResponse,
    CaseUpdate,
    EvidenceCaptureRequest,
    EvidenceCaptureResponse,
    EvidenceFileResponse,
)
from app.schemas.common import PaginatedResponse
from app.services.evidence_capture_service import EvidenceCaptureService
from app.services.evidence_integrity_service import EvidenceIntegrityService
from app.services.file_storage_service import FileStorageService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cases"])

integrity_svc = EvidenceIntegrityService()


async def _get_case_with_access(
    case_id: uuid.UUID, db: AsyncSession, user: User
) -> InfringementCase:
    """소유권 검증 포함 case 조회."""
    result = await db.execute(
        select(InfringementCase)
        .join(Organization, InfringementCase.organization_id == Organization.id)
        .where(
            InfringementCase.id == case_id,
            Organization.owner_id == user.id,
        )
    )
    case = result.scalar_one_or_none()
    if not case:
        raise NotFoundError("Case")
    return case


async def _verify_org_access(
    org_id: uuid.UUID, db: AsyncSession, user: User
) -> None:
    result = await db.execute(
        select(Organization).where(
            Organization.id == org_id,
            Organization.owner_id == user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise ForbiddenError("No access to this organization")


@router.get(
    "/organizations/{org_id}/cases",
    response_model=PaginatedResponse[CaseResponse],
)
async def list_cases(
    org_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_org_access(org_id, db, current_user)

    base_query = select(InfringementCase).where(
        InfringementCase.organization_id == org_id
    )
    if status:
        base_query = base_query.where(InfringementCase.status == status)

    total_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(
        base_query.order_by(InfringementCase.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    cases = result.scalars().all()

    return PaginatedResponse.create(
        items=[CaseResponse.model_validate(c) for c in cases],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/cases/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await _get_case_with_access(case_id, db, current_user)
    return CaseResponse.model_validate(case)


@router.patch("/cases/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: uuid.UUID,
    body: CaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = await _get_case_with_access(case_id, db, current_user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(case, field, value)
    await db.flush()
    await db.refresh(case)
    return CaseResponse.model_validate(case)


@router.get("/cases/{case_id}/evidence", response_model=list[EvidenceFileResponse])
async def list_evidence(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_case_with_access(case_id, db, current_user)
    result = await db.execute(
        select(EvidenceFile)
        .where(EvidenceFile.infringement_case_id == case_id)
        .order_by(EvidenceFile.created_at.desc())
    )
    return [EvidenceFileResponse.model_validate(e) for e in result.scalars().all()]


# ── 08: 증거 캡처 ────────────────────────────────


@router.post(
    "/cases/{case_id}/evidence/capture",
    response_model=EvidenceCaptureResponse,
    status_code=201,
)
async def capture_evidence(
    case_id: uuid.UUID,
    body: EvidenceCaptureRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    capture_svc: EvidenceCaptureService = Depends(get_evidence_capture_service),
    file_storage: FileStorageService = Depends(get_file_storage_service),
):
    """의심 URL의 증거를 캡처한다.

    1. Playwright로 페이지 캡처 (스크린샷 + HTML + 이미지 URL 추출)
    2. 페이지 내 이미지 다운로드
    3. EvidenceFile 레코드 생성 (SHA-256 해시 포함)
    4. Merkle root 증거 체인 생성
    """
    case = await _get_case_with_access(case_id, db, current_user)

    url = body.url or case.suspect_url
    if not url:
        raise BadRequestError("No URL provided and case has no suspect_url")

    # SSRF 방지 (DNS 리졸브 후 내부 IP 차단)
    if not is_ssrf_safe_url(url):
        raise BadRequestError("URL is not allowed (internal or invalid)")

    if not capture_svc.enabled:
        raise BadRequestError("Evidence capture service is not available (Playwright not installed)")

    # ── [1] 페이지 캡처 ──
    capture_result = await capture_svc.capture_page(url)
    if not capture_result:
        raise BadRequestError(f"Failed to capture page: {url}")

    now = datetime.now(timezone.utc)
    all_hashes: list[str] = []
    evidence_records: list[EvidenceFile] = []

    # ── [2] 스크린샷 증거 ──
    screenshot_hash = integrity_svc.hash_bytes(capture_result.screenshot_bytes)
    all_hashes.append(screenshot_hash)

    screenshot_ef = EvidenceFile(
        infringement_case_id=case.id,
        file_type="webpage_screenshot",
        file_storage_key=f"evidence/{case.id}/screenshot/{screenshot_hash[:8]}.png",
        file_name=f"screenshot_{capture_result.page_title[:50]}.png",
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

    # ── [3] HTML 스냅샷 증거 ──
    html_bytes = capture_result.html_content.encode("utf-8")
    html_hash = integrity_svc.hash_bytes(html_bytes)
    all_hashes.append(html_hash)

    html_ef = EvidenceFile(
        infringement_case_id=case.id,
        file_type="html_snapshot",
        file_storage_key=f"evidence/{case.id}/html/{html_hash[:8]}.html",
        file_name=f"snapshot_{capture_result.page_title[:50]}.html",
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

    # ── [4] 이미지 다운로드 + 증거 ──
    downloaded = await capture_svc.download_images(capture_result.image_urls)

    _SAFE_EXTENSIONS = {"jpeg": "jpg", "jpg": "jpg", "png": "png", "webp": "webp", "gif": "gif"}

    for img in downloaded:
        all_hashes.append(img.sha256_hash)

        # 파일명: URL의 마지막 경로 세그먼트
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

    # ── [5] Merkle root 증거 체인 ──
    chain = integrity_svc.create_evidence_chain(all_hashes)

    # case의 suspect_url 업데이트 (아직 없었다면)
    if not case.suspect_url:
        case.suspect_url = url

    await db.flush()
    for ef in evidence_records:
        await db.refresh(ef)

    logger.info(
        "Evidence captured for case %s: %d files, merkle_root=%s",
        case.case_number,
        len(evidence_records),
        chain["merkle_root"][:16],
    )

    return EvidenceCaptureResponse(
        case_id=case.id,
        captured_url=url,
        page_title=capture_result.page_title,
        images_found=len(capture_result.image_urls),
        images_downloaded=len(downloaded),
        evidence_files_created=len(evidence_records),
        merkle_root=chain["merkle_root"],
        captured_at=now,
        evidence_files=[EvidenceFileResponse.model_validate(ef) for ef in evidence_records],
    )
