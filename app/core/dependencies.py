import uuid

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_access_token
from app.models.user import User
from app.services.analysis_service import AnalysisService
from app.services.c2pa_service import C2paService
from app.services.evidence_capture_service import EvidenceCaptureService
from app.services.file_storage_service import FileStorageService
from app.services.qstash_service import QStashService
from app.services.redis_service import RedisService
from app.services.stegai_service import StegAIService

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise UnauthorizedError("Invalid or expired token")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    return user


def get_stegai_service(request: Request) -> StegAIService:
    return request.app.state.stegai


def get_c2pa_service(request: Request) -> C2paService:
    return request.app.state.c2pa


def get_analysis_service(request: Request) -> AnalysisService:
    return request.app.state.analysis


def get_evidence_capture_service(request: Request) -> EvidenceCaptureService:
    return request.app.state.evidence_capture


def get_qstash_service(request: Request) -> QStashService:
    return request.app.state.qstash


def get_redis_service(request: Request) -> RedisService:
    return request.app.state.redis


def get_file_storage_service(request: Request) -> FileStorageService:
    return request.app.state.file_storage
