"""이미지 분석 파이프라인 결과 스키마."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class FingerprintResult(BaseModel):
    """이미지 지문 생성 결과 (내부용)."""

    phash_hex: str | None = None
    clip_vector: list[float] | None = None
    dino_vector: list[float] | None = None


class SimilarCandidate(BaseModel):
    """유사 원본 후보."""

    original_image_id: uuid.UUID
    image_id: str | None = None  # RP-IMG-YYYYMMDD-XXXXXX
    similarity_phash: float | None = None
    similarity_clip: float | None = None
    similarity_dino: float | None = None
    overall_score: float
    risk_level: str  # high, medium, low


class FeatureMatchResult(BaseModel):
    """ORB 피처 매칭 결과 (내부용)."""

    num_matches: int = 0
    good_matches: int = 0
    match_visualization_bytes: bytes | None = None

    model_config = {"arbitrary_types_allowed": True}


class AnalysisResult(BaseModel):
    """의심 이미지 분석 결과."""

    candidates: list[SimilarCandidate] = []
    phash_hex: str | None = None
    best_score: float = 0.0
    best_risk_level: str = "low"
