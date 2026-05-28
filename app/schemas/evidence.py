"""증거 보존 시스템 내부 스키마."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PageCaptureResult(BaseModel):
    """Playwright 페이지 캡처 결과 (내부용)."""

    screenshot_bytes: bytes
    html_content: str
    image_urls: list[str]
    page_title: str
    final_url: str
    captured_at: datetime

    model_config = {"arbitrary_types_allowed": True}


class DownloadedImage(BaseModel):
    """다운로드된 이미지 (내부용)."""

    url: str
    image_bytes: bytes
    mime_type: str
    sha256_hash: str

    model_config = {"arbitrary_types_allowed": True}


class ComparisonResult(BaseModel):
    """비교 이미지 생성 결과 (내부용)."""

    side_by_side_bytes: bytes | None = None
    diff_overlay_bytes: bytes | None = None

    model_config = {"arbitrary_types_allowed": True}


class EvidenceChainResult(BaseModel):
    """증거 체인 무결성 결과."""

    evidence_count: int
    hashes: list[str]
    merkle_root: str
    created_at: datetime
