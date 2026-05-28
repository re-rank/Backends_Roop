import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.organization import Organization
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    body: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = Organization(owner_id=current_user.id, **body.model_dump())
    db.add(org)
    await db.flush()
    await db.refresh(org)
    return OrganizationResponse.model_validate(org)


@router.get("", response_model=PaginatedResponse[OrganizationResponse])
async def list_organizations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base_query = select(Organization).where(Organization.owner_id == current_user.id)

    total_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(
        base_query.order_by(Organization.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    orgs = result.scalars().all()

    return PaginatedResponse.create(
        items=[OrganizationResponse.model_validate(o) for o in orgs],
        total=total,
        page=page,
        page_size=page_size,
    )


async def _get_org_or_404(org_id: uuid.UUID, db: AsyncSession, user: User) -> Organization:
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundError("Organization")
    if org.owner_id != user.id:
        raise ForbiddenError()
    return org


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = await _get_org_or_404(org_id, db, current_user)
    return OrganizationResponse.model_validate(org)


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: uuid.UUID,
    body: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = await _get_org_or_404(org_id, db, current_user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    await db.flush()
    await db.refresh(org)
    return OrganizationResponse.model_validate(org)


@router.delete("/{org_id}", status_code=204)
async def delete_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = await _get_org_or_404(org_id, db, current_user)
    await db.delete(org)
