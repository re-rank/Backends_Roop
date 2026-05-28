import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.case import InfringementCase
from app.models.detection import DetectionRequest
from app.models.image import OriginalImage, ProtectedImage
from app.models.project import Project
from app.models.user import User

router = APIRouter(tags=["dashboard"])


@router.get("/organizations/{org_id}/dashboard/stats")
async def get_dashboard_stats(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 등록 이미지 수
    img_count = await db.execute(
        select(func.count())
        .select_from(OriginalImage)
        .join(Project, OriginalImage.project_id == Project.id)
        .where(Project.organization_id == org_id)
    )

    # 보호 완료 수
    protected_count = await db.execute(
        select(func.count())
        .select_from(ProtectedImage)
        .join(OriginalImage, ProtectedImage.original_image_id == OriginalImage.id)
        .join(Project, OriginalImage.project_id == Project.id)
        .where(Project.organization_id == org_id)
    )

    # 진행 중 사건 수
    open_cases = await db.execute(
        select(func.count())
        .select_from(InfringementCase)
        .where(
            InfringementCase.organization_id == org_id,
            InfringementCase.status.in_(["open", "investigating"]),
        )
    )

    # 분석 요청 수
    detection_count = await db.execute(
        select(func.count())
        .select_from(DetectionRequest)
        .where(DetectionRequest.organization_id == org_id)
    )

    return {
        "total_images": img_count.scalar() or 0,
        "protected_images": protected_count.scalar() or 0,
        "open_cases": open_cases.scalar() or 0,
        "total_detections": detection_count.scalar() or 0,
    }


@router.get("/organizations/{org_id}/dashboard/recent-cases")
async def get_recent_cases(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(InfringementCase)
        .where(InfringementCase.organization_id == org_id)
        .order_by(InfringementCase.created_at.desc())
        .limit(10)
    )
    cases = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "case_number": c.case_number,
            "title": c.title,
            "status": c.status,
            "overall_score": c.overall_score,
            "suspect_platform": c.suspect_platform,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in cases
    ]
