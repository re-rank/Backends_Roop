"""이미지 분석 파이프라인 오케스트레이터.

3단계 파이프라인:
  [1차] pHash — 단순 도용 빠른 탐지 (ms 단위)
  [2차] CLIP + DINOv2 벡터 검색 — AI 변형 대응 (초 단위)
  [3차] ORB 피처 매칭 — 시각적 증거 생성 (on-demand)

종합 점수: pHash 0.2 + CLIP 0.4 + DINO 0.4 (가중 합산)
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.image import OriginalImage
from app.schemas.analysis import AnalysisResult, FingerprintResult, SimilarCandidate
from app.services.embedding_service import EmbeddingService
from app.services.feature_match_service import FeatureMatchService
from app.services.phash_service import PHashService
from app.services.vector_search_service import VectorSearchService

logger = logging.getLogger(__name__)

# 가중치
WEIGHTS = {"phash": 0.2, "clip": 0.4, "dino": 0.4}


def calculate_overall_score(
    phash_sim: float | None,
    clip_sim: float | None,
    dino_sim: float | None,
    watermark_detected: bool = False,
) -> tuple[float, str]:
    """가중 합산 점수 및 위험도 판정.

    Returns:
        (overall_score, risk_level)
    """
    if watermark_detected:
        return 1.0, "high"

    total_weight = 0.0
    score = 0.0

    for key, sim in [("phash", phash_sim), ("clip", clip_sim), ("dino", dino_sim)]:
        if sim is not None:
            score += sim * WEIGHTS[key]
            total_weight += WEIGHTS[key]

    if total_weight > 0:
        score /= total_weight  # 사용 가능한 신호 기준 정규화
    else:
        return 0.0, "low"

    if score >= 0.85:
        risk = "high"
    elif score >= 0.65:
        risk = "medium"
    else:
        risk = "low"

    return round(score, 4), risk


class AnalysisService:
    """3단계 이미지 분석 파이프라인."""

    def __init__(
        self,
        phash_svc: PHashService,
        embedding_svc: EmbeddingService,
        vector_search_svc: VectorSearchService,
        feature_match_svc: FeatureMatchService,
    ) -> None:
        self.phash = phash_svc
        self.embedding = embedding_svc
        self.vector_search = vector_search_svc
        self.feature_match = feature_match_svc

    # ── 지문 생성 (이미지 등록 시) ────────────────────

    async def generate_fingerprint(
        self,
        image_bytes: bytes,
        original_image_id: uuid.UUID,
        organization_id: str | None = None,
        image_id: str | None = None,
    ) -> FingerprintResult:
        """원본 이미지의 지문(pHash + 벡터)을 생성하고 Qdrant에 업서트.

        빈 바이트 시 모든 필드가 None인 결과를 반환한다.
        """
        result = FingerprintResult()

        if not image_bytes:
            logger.warning("Empty image bytes — skipping fingerprint generation")
            return result

        # pHash (빠름, ~10ms)
        result.phash_hex = await self.phash.generate_phash(image_bytes)

        # CLIP + DINOv2 임베딩 (느림, ~500ms~2s CPU)
        result.clip_vector = await self.embedding.get_clip_embedding(image_bytes)
        result.dino_vector = await self.embedding.get_dino_embedding(image_bytes)

        # Qdrant 업서트
        metadata: dict = {}
        if organization_id:
            metadata["organization_id"] = organization_id
        if image_id:
            metadata["image_id"] = image_id

        await self.vector_search.upsert_vectors(
            original_image_id=original_image_id,
            clip_vector=result.clip_vector,
            dino_vector=result.dino_vector,
            metadata=metadata,
        )

        logger.info(
            "Fingerprint generated for %s: phash=%s, clip=%s, dino=%s",
            image_id or original_image_id,
            "yes" if result.phash_hex else "no",
            "yes" if result.clip_vector else "no",
            "yes" if result.dino_vector else "no",
        )
        return result

    # ── 의심 이미지 분석 ──────────────────────────────

    async def analyze_suspect(
        self,
        suspect_bytes: bytes,
        organization_id: str | None,
        db: AsyncSession,
    ) -> AnalysisResult:
        """의심 이미지를 3단계 파이프라인으로 분석.

        Returns:
            유사 원본 후보 목록 (점수 내림차순, 최대 20개)
        """
        result = AnalysisResult()

        if not suspect_bytes:
            return result

        # ── [1차] pHash 비교 ──
        phash_hex = await self.phash.generate_phash(suspect_bytes)
        result.phash_hex = phash_hex

        phash_candidates: dict[uuid.UUID, float] = {}
        if phash_hex:
            phash_candidates = await self._search_by_phash(
                phash_hex, db, organization_id=organization_id
            )

        # ── [2차] CLIP + DINO 벡터 검색 ──
        clip_vec = await self.embedding.get_clip_embedding(suspect_bytes)
        dino_vec = await self.embedding.get_dino_embedding(suspect_bytes)

        vector_results = await self.vector_search.search_similar(
            clip_vector=clip_vec,
            dino_vector=dino_vec,
            organization_id=organization_id,
        )

        clip_scores: dict[str, float] = dict(vector_results.get("clip", []))
        dino_scores: dict[str, float] = dict(vector_results.get("dino", []))

        # ── 결과 융합 ──
        all_id_strs: set[str] = set()
        all_id_strs.update(str(cid) for cid in phash_candidates)
        all_id_strs.update(clip_scores)
        all_id_strs.update(dino_scores)

        # UUID 변환 + 일괄 image_id 조회 (N+1 방지)
        valid_uuids: list[uuid.UUID] = []
        for s in all_id_strs:
            try:
                valid_uuids.append(uuid.UUID(s))
            except ValueError:
                continue

        image_id_map: dict[uuid.UUID, str] = {}
        if valid_uuids:
            rows = await db.execute(
                select(OriginalImage.id, OriginalImage.image_id).where(
                    OriginalImage.id.in_(valid_uuids)
                )
            )
            image_id_map = {row.id: row.image_id for row in rows}

        candidates: list[SimilarCandidate] = []
        for cid in valid_uuids:
            cid_str = str(cid)

            phash_sim = phash_candidates.get(cid)
            clip_sim = clip_scores.get(cid_str)
            dino_sim = dino_scores.get(cid_str)

            overall, risk = calculate_overall_score(phash_sim, clip_sim, dino_sim)

            candidates.append(
                SimilarCandidate(
                    original_image_id=cid,
                    image_id=image_id_map.get(cid),
                    similarity_phash=round(phash_sim, 4) if phash_sim is not None else None,
                    similarity_clip=round(clip_sim, 4) if clip_sim is not None else None,
                    similarity_dino=round(dino_sim, 4) if dino_sim is not None else None,
                    overall_score=overall,
                    risk_level=risk,
                )
            )

        candidates.sort(key=lambda c: c.overall_score, reverse=True)
        result.candidates = candidates[:20]

        if candidates:
            result.best_score = candidates[0].overall_score
            result.best_risk_level = candidates[0].risk_level

        return result

    # ── 내부: pHash DB 검색 ───────────────────────────

    async def _search_by_phash(
        self,
        target_hash: str,
        db: AsyncSession,
        organization_id: str | None = None,
        threshold: float = 0.80,
    ) -> dict[uuid.UUID, float]:
        """DB에서 pHash 유사 이미지 검색.

        PostgreSQL bit_count(XOR) 활용하여 DB 레벨에서 해밍 거리를 계산한다.
        threshold=0.80 → 최대 해밍 거리 = (1 - 0.80) * 64 = 12
        """
        target_bits = PHashService.phash_hex_to_bits(target_hash)
        if not target_bits:
            return {}

        max_distance = int((1.0 - threshold) * 64)

        sql = """
            SELECT fp.original_image_id,
                   1.0 - (bit_count(fp.phash_binary # :target_bits) / 64.0) AS similarity
            FROM image_fingerprints fp
            JOIN original_images oi ON fp.original_image_id = oi.id
        """
        params: dict = {"target_bits": target_bits, "max_dist": max_distance}

        if organization_id:
            sql += """
            JOIN projects p ON oi.project_id = p.id
            WHERE fp.phash_binary IS NOT NULL
              AND p.organization_id = :org_id
              AND bit_count(fp.phash_binary # :target_bits) <= :max_dist
            """
            params["org_id"] = organization_id
        else:
            sql += """
            WHERE fp.phash_binary IS NOT NULL
              AND bit_count(fp.phash_binary # :target_bits) <= :max_dist
            """

        sql += " ORDER BY similarity DESC"

        result = await db.execute(text(sql), params)
        rows = result.all()

        return {row.original_image_id: float(row.similarity) for row in rows}
