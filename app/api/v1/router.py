from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.cases import router as cases_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.detection import router as detection_router
from app.api.v1.images import router as images_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.workers import router as workers_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.projects import router as projects_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(organizations_router)
api_router.include_router(projects_router)
api_router.include_router(images_router)
api_router.include_router(detection_router)
api_router.include_router(cases_router)
api_router.include_router(dashboard_router)
api_router.include_router(jobs_router)
api_router.include_router(workers_router)


@api_router.get("/ping")
async def ping():
    return {"message": "pong"}
