"""MongoDB GridFS 기반 파일 스토리지 서비스.

이미지·증거 파일의 바이너리 데이터를 GridFS에 저장하고 조회한다.
storage_key(파일명)로 식별하며, 메타데이터를 함께 저장할 수 있다.
"""

from __future__ import annotations

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

logger = logging.getLogger(__name__)


class FileStorageService:
    """Motor/GridFS 파일 저장소."""

    def __init__(self, uri: str, db_name: str) -> None:
        self.enabled = bool(uri)
        self._client: AsyncIOMotorClient | None = None
        self._bucket: AsyncIOMotorGridFSBucket | None = None

        if self.enabled:
            try:
                self._client = AsyncIOMotorClient(uri)
                db = self._client[db_name]
                self._bucket = AsyncIOMotorGridFSBucket(db)
            except Exception:
                logger.warning("MongoDB GridFS init failed — file storage disabled")
                self.enabled = False

    async def store(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
        metadata: dict | None = None,
    ) -> str:
        """파일을 GridFS에 저장한다.

        같은 key로 이미 존재하면 기존 파일을 삭제 후 덮어쓴다.

        Returns:
            저장된 storage_key
        """
        if not self.enabled or not data:
            return key

        # 기존 파일 삭제 (덮어쓰기)
        await self._delete_by_key(key)

        grid_metadata = metadata or {}
        if content_type:
            grid_metadata["content_type"] = content_type

        await self._bucket.upload_from_stream(
            key,
            data,
            metadata=grid_metadata if grid_metadata else None,
        )
        logger.debug("Stored file: %s (%d bytes)", key, len(data))
        return key

    async def get(self, key: str) -> bytes | None:
        """GridFS에서 파일 바이트를 조회한다.

        Returns:
            파일 바이트 또는 None (미존재 / 비활성)
        """
        if not self.enabled:
            return None

        try:
            grid_out = await self._bucket.open_download_stream_by_name(key)
            return await grid_out.read()
        except Exception:
            logger.debug("File not found in GridFS: %s", key)
            return None

    async def delete(self, key: str) -> bool:
        """GridFS에서 파일을 삭제한다."""
        if not self.enabled:
            return False
        return await self._delete_by_key(key)

    async def exists(self, key: str) -> bool:
        """파일 존재 여부 확인."""
        if not self.enabled:
            return False
        cursor = self._bucket.find({"filename": key}, limit=1)
        async for _ in cursor:
            return True
        return False

    async def close(self) -> None:
        """MongoDB 연결 종료."""
        if self._client:
            self._client.close()

    # ── 헬스체크 ─────────────────────────────────

    async def ping(self) -> bool:
        """MongoDB 연결 상태 확인."""
        if not self._client:
            return False
        try:
            await self._client.admin.command("ping")
            return True
        except Exception:
            return False

    # ── 내부 ─────────────────────────────────────

    async def _delete_by_key(self, key: str) -> bool:
        """filename으로 GridFS 파일을 모두 삭제."""
        deleted = False
        cursor = self._bucket.find({"filename": key})
        async for grid_out in cursor:
            await self._bucket.delete(grid_out._id)
            deleted = True
        return deleted
