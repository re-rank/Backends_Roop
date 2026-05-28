"""작업 상태 조회 API.

프론트엔드에서 폴링하여 비동기 작업의 진행 상태를 확인한다.
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user, get_redis_service
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.services.redis_service import RedisService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}/status")
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    redis_svc: RedisService = Depends(get_redis_service),
):
    """작업 상태를 조회한다.

    Redis에 저장된 작업 해시를 반환한다.
    status: queued | processing | completed | failed
    """
    if not redis_svc.enabled:
        raise NotFoundError("Job tracking")

    job = await redis_svc.get_job(job_id)
    if not job:
        raise NotFoundError("Job")

    # 소유권 검증: job의 owner_id가 현재 사용자와 일치하는지 확인
    job_owner = job.get("meta:owner_id", "")
    if job_owner and job_owner != str(current_user.id):
        raise NotFoundError("Job")

    # meta:/result: prefix 정리하여 깔끔한 응답 구성
    response: dict = {}
    meta: dict = {}
    result: dict = {}

    for k, v in job.items():
        if k.startswith("meta:"):
            meta[k[5:]] = v
        elif k.startswith("result:"):
            result[k[7:]] = v
        else:
            response[k] = v

    if meta:
        response["metadata"] = meta
    if result:
        response["result"] = result

    return response
