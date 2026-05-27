import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.organization import Organization
from app.models.project import Project
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(tags=["projects"])


async def _verify_org_access(org_id: uuid.UUID, db: AsyncSession, user: User) -> Organization:
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundError("Organization")
    if org.owner_id != user.id:
        raise ForbiddenError()
    return org


async def _get_project_or_404(project_id: uuid.UUID, db: AsyncSession, user: User) -> Project:
    result = await db.execute(
        select(Project)
        .join(Organization, Project.organization_id == Organization.id)
        .where(Project.id == project_id, Organization.owner_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundError("Project")
    return project


@router.post(
    "/organizations/{org_id}/projects",
    response_model=ProjectResponse,
    status_code=201,
)
async def create_project(
    org_id: uuid.UUID,
    body: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_org_access(org_id, db, current_user)
    project = Project(organization_id=org_id, **body.model_dump())
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get(
    "/organizations/{org_id}/projects",
    response_model=PaginatedResponse[ProjectResponse],
)
async def list_projects(
    org_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_org_access(org_id, db, current_user)

    base_query = select(Project).where(
        Project.organization_id == org_id, Project.status == "active"
    )
    total_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(
        base_query.order_by(Project.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    projects = result.scalars().all()

    return PaginatedResponse.create(
        items=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project_or_404(project_id, db, current_user)
    return ProjectResponse.model_validate(project)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project_or_404(project_id, db, current_user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = await _get_project_or_404(project_id, db, current_user)
    await db.delete(project)
