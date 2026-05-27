"""Qdrant 벡터 업서트/검색 서비스.

Qdrant 미실행 시 graceful degradation (enabled=False).
동기 QdrantClient를 asyncio.to_thread로 래핑.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)

CLIP_COLLECTION = "reproof_clip"
DINO_COLLECTION = "reproof_dino"
CLIP_DIM = 512
DINO_DIM = 768


class VectorSearchService:
    """Qdrant 벡터 업서트/검색 서비스."""

    def __init__(self, url: str, api_key: str = "") -> None:
        self.enabled = False
        self._client: QdrantClient | None = None
        try:
            kwargs: dict = {"url": url, "timeout": 10}
            if api_key:
                kwargs["api_key"] = api_key
            self._client = QdrantClient(**kwargs)
            self._client.get_collections()  # connection test
            self.enabled = True
            logger.info("Qdrant connected: %s", url)
        except Exception:
            self._client = None
            logger.warning(
                "Qdrant connection failed (%s) — vector search disabled", url
            )

    # ── 컬렉션 초기화 ────────────────────────────────

    def ensure_collections(self) -> None:
        """CLIP/DINO 컬렉션이 없으면 생성."""
        if not self.enabled or not self._client:
            return
        try:
            existing = {
                c.name for c in self._client.get_collections().collections
            }
            for name, dim in [
                (CLIP_COLLECTION, CLIP_DIM),
                (DINO_COLLECTION, DINO_DIM),
            ]:
                if name not in existing:
                    self._client.create_collection(
                        collection_name=name,
                        vectors_config=models.VectorParams(
                            size=dim, distance=models.Distance.COSINE
                        ),
                    )
                    logger.info("Created Qdrant collection: %s (%dd)", name, dim)
        except Exception:
            logger.exception("Failed to ensure Qdrant collections")

    # ── 동기 (to_thread용) ────────────────────────────

    def _upsert_sync(
        self,
        original_image_id: uuid.UUID,
        clip_vector: list[float] | None,
        dino_vector: list[float] | None,
        metadata: dict,
    ) -> None:
        if not self._client:
            return
        point_id = str(original_image_id)
        if clip_vector:
            self._client.upsert(
                collection_name=CLIP_COLLECTION,
                points=[
                    models.PointStruct(
                        id=point_id, vector=clip_vector, payload=metadata
                    )
                ],
            )
        if dino_vector:
            self._client.upsert(
                collection_name=DINO_COLLECTION,
                points=[
                    models.PointStruct(
                        id=point_id, vector=dino_vector, payload=metadata
                    )
                ],
            )

    def _search_sync(
        self,
        clip_vector: list[float] | None,
        dino_vector: list[float] | None,
        organization_id: str | None,
        top_k: int,
    ) -> dict[str, list[tuple[str, float]]]:
        results: dict[str, list[tuple[str, float]]] = {
            "clip": [],
            "dino": [],
        }
        if not self._client:
            return results

        query_filter = None
        if organization_id:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="organization_id",
                        match=models.MatchValue(value=organization_id),
                    )
                ]
            )

        if clip_vector:
            hits = self._client.search(
                collection_name=CLIP_COLLECTION,
                query_vector=clip_vector,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=0.5,
            )
            results["clip"] = [(str(h.id), h.score) for h in hits]

        if dino_vector:
            hits = self._client.search(
                collection_name=DINO_COLLECTION,
                query_vector=dino_vector,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=0.5,
            )
            results["dino"] = [(str(h.id), h.score) for h in hits]

        return results

    # ── 비동기 ────────────────────────────────────────

    async def upsert_vectors(
        self,
        original_image_id: uuid.UUID,
        clip_vector: list[float] | None,
        dino_vector: list[float] | None,
        metadata: dict,
    ) -> None:
        """벡터 업서트. 미연결 시 skip."""
        if not self.enabled:
            return
        try:
            await asyncio.to_thread(
                self._upsert_sync,
                original_image_id,
                clip_vector,
                dino_vector,
                metadata,
            )
        except Exception:
            logger.exception("Qdrant upsert failed")

    async def search_similar(
        self,
        clip_vector: list[float] | None,
        dino_vector: list[float] | None,
        organization_id: str | None = None,
        top_k: int = 10,
    ) -> dict[str, list[tuple[str, float]]]:
        """유사 벡터 검색. 미연결 시 빈 결과."""
        if not self.enabled:
            return {"clip": [], "dino": []}
        try:
            return await asyncio.to_thread(
                self._search_sync,
                clip_vector,
                dino_vector,
                organization_id,
                top_k,
            )
        except Exception:
            logger.exception("Qdrant search failed")
            return {"clip": [], "dino": []}

    def is_healthy(self) -> bool:
        """Qdrant 연결 상태 확인."""
        if not self._client:
            return False
        try:
            self._client.get_collections()
            return True
        except Exception:
            return False

    def close(self) -> None:
        """클라이언트 종료."""
        if self._client:
            self._client.close()
