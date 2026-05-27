"""Upstash Redis 기반 작업 상태 추적 서비스.

작업(job)의 진행 상태를 Redis Hash에 저장하고 프론트엔드 폴링으로 조회한다.
키 패턴: job:{job_id} — TTL 24시간
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from upstash_redis.asyncio import Redis

logger = logging.getLogger(__name__)

JOB_TTL_SECONDS = 86_400  # 24h


class RedisService:
    """Upstash Redis 작업 상태 관리."""

    def __init__(self, url: str, token: str) -> None:
        self.enabled = bool(url and token)
        self._client: Redis | None = None
        if self.enabled:
            try:
                self._client = Redis(url=url, token=token)
            except Exception:
                logger.warning("Redis client init failed — disabled")
                self.enabled = False

    # ── 작업 생성 ───────────────────────────────
    async def create_job(
        self,
        job_id: str,
        job_type: str,
        *,
        metadata: dict | None = None,
    ) -> None:
        if not self.enabled:
            return
        key = f"job:{job_id}"
        data: dict[str, str] = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "queued",
            "progress": "0",
            "step": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            for k, v in metadata.items():
                data[f"meta:{k}"] = str(v)
        await self._client.hset(key, values=data)
        await self._client.expire(key, JOB_TTL_SECONDS)

    # ── 상태 갱신 ───────────────────────────────
    async def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        step: str | None = None,
        progress: int | None = None,
        error: str | None = None,
    ) -> None:
        if not self.enabled:
            return
        key = f"job:{job_id}"
        updates: dict[str, str] = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if status is not None:
            updates["status"] = status
        if step is not None:
            updates["step"] = step
        if progress is not None:
            updates["progress"] = str(progress)
        if error is not None:
            updates["error"] = error
        await self._client.hset(key, values=updates)
        await self._client.expire(key, JOB_TTL_SECONDS)

    # ── 상태 조회 ───────────────────────────────
    async def get_job(self, job_id: str) -> dict | None:
        if not self.enabled:
            return None
        key = f"job:{job_id}"
        data = await self._client.hgetall(key)
        if not data:
            return None
        return data

    # ── 작업 완료 ───────────────────────────────
    async def complete_job(
        self,
        job_id: str,
        *,
        result: dict | None = None,
    ) -> None:
        if not self.enabled:
            return
        key = f"job:{job_id}"
        data: dict[str, str] = {
            "status": "completed",
            "progress": "100",
            "step": "done",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if result:
            for k, v in result.items():
                data[f"result:{k}"] = str(v)
        await self._client.hset(key, values=data)
        await self._client.expire(key, JOB_TTL_SECONDS)

    async def fail_job(self, job_id: str, error: str) -> None:
        await self.update_job(job_id, status="failed", step="error", error=error)
