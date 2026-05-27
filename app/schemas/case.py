import uuid
from datetime import datetime

from pydantic import BaseModel


class CaseUpdate(BaseModel):
    status: str | None = None
    title: str | None = None
    notes: str | None = None


class CaseResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    detected_match_id: uuid.UUID | None
    case_number: str
    title: str | None
    status: str
    suspect_url: str | None
    suspect_seller_name: str | None
    suspect_platform: str | None
    overall_score: float | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EvidenceFileResponse(BaseModel):
    id: uuid.UUID
    infringement_case_id: uuid.UUID
    file_type: str
    file_storage_key: str
    file_name: str | None
    sha256_hash: str | None
    captured_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LegalDocumentResponse(BaseModel):
    id: uuid.UUID
    infringement_case_id: uuid.UUID
    document_type: str
    file_storage_key: str
    generated_at: datetime

    model_config = {"from_attributes": True}


# ── 08: 증거 캡처 ────────────────────────────────


class EvidenceCaptureRequest(BaseModel):
    """증거 캡처 요청. URL 미입력 시 case.suspect_url 사용."""

    url: str | None = None


class EvidenceCaptureResponse(BaseModel):
    """증거 캡처 결과 요약."""

    case_id: uuid.UUID
    captured_url: str
    page_title: str
    images_found: int
    images_downloaded: int
    evidence_files_created: int
    merkle_root: str
    captured_at: datetime
    evidence_files: list[EvidenceFileResponse] = []
