"""
C2PA manifest 생성 및 검증 서비스.

c2pa-python (동기 API) 을 asyncio.to_thread 로 래핑하여 비동기 제공.
개발용 self-signed 인증서를 사용하며, 프로덕션에서는 CA 발급 인증서로 교체.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import c2pa
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.schemas.c2pa import C2paMetadata, C2paVerifyResult

logger = logging.getLogger(__name__)


class C2paService:
    """C2PA manifest 생성/읽기/검증 서비스."""

    def __init__(self, cert_path: str, key_path: str) -> None:
        self.cert_path = Path(cert_path)
        self.key_path = Path(key_path)
        self.enabled = self.cert_path.exists() and self.key_path.exists()
        self._signer: c2pa.Signer | None = None

        if not self.enabled:
            logger.warning(
                "C2PA signing disabled: cert=%s key=%s (files not found)",
                cert_path,
                key_path,
            )

    def _get_signer(self) -> c2pa.Signer:
        if self._signer is None:
            cert_pem = self.cert_path.read_text()
            key_pem = self.key_path.read_text()

            private_key = serialization.load_pem_private_key(
                key_pem.encode(), password=None
            )

            def sign_callback(data: bytes) -> bytes:
                return private_key.sign(data, ec.ECDSA(hashes.SHA256()))

            self._signer = c2pa.Signer.from_callback(
                callback=sign_callback,
                alg=c2pa.C2paSigningAlg.ES256,
                certs=cert_pem,
                tsa_url=None,
            )
        return self._signer

    # ── Manifest 생성 ────────────────────────────────────────

    def _create_manifest_sync(
        self,
        image_bytes: bytes,
        mime_type: str,
        metadata: C2paMetadata,
    ) -> bytes:
        """동기: 이미지에 C2PA manifest를 삽입하고 서명된 이미지 바이트 반환."""
        now = datetime.now(timezone.utc).isoformat()

        # C2PA manifest에는 표준 assertion만 포함
        # Re-Proof 커스텀 메타데이터는 DB (c2pa_manifests.manifest_data)에 저장
        manifest_json = {
            "claim_generator": "Re-Proof Image Protection Engine/1.0",
            "title": metadata.asset_id,
            "assertions": [
                {
                    "label": "stds.schema-org.CreativeWork",
                    "data": {
                        "@context": "https://schema.org",
                        "@type": "CreativeWork",
                        "author": [
                            {
                                "@type": "Organization",
                                "name": "Re-Proof",
                            }
                        ],
                    },
                },
                {
                    "label": "c2pa.actions",
                    "data": {
                        "actions": [
                            {
                                "action": "c2pa.created",
                                "when": now,
                                "softwareAgent": "Re-Proof Image Protection Engine",
                            }
                        ]
                    },
                },
            ],
        }

        builder = c2pa.Builder(json.dumps(manifest_json))
        signer = self._get_signer()

        source = io.BytesIO(image_bytes)
        dest = io.BytesIO()
        builder.sign(signer, mime_type, source, dest)

        return dest.getvalue()

    async def create_manifest(
        self,
        image_bytes: bytes,
        mime_type: str,
        metadata: C2paMetadata,
    ) -> bytes | None:
        """
        이미지에 C2PA manifest를 삽입한다.

        Returns:
            서명된 이미지 바이트 또는 실패/미설정 시 None
        """
        if not self.enabled:
            logger.warning("C2PA signing disabled — skipping manifest creation")
            return None

        try:
            return await asyncio.to_thread(
                self._create_manifest_sync, image_bytes, mime_type, metadata
            )
        except Exception:
            logger.exception("C2PA manifest creation failed")
            return None

    # ── Manifest 읽기/검증 ────────────────────────────────────

    def _read_manifest_sync(
        self,
        image_bytes: bytes,
        mime_type: str,
    ) -> C2paVerifyResult:
        """동기: 이미지에서 C2PA manifest를 읽고 검증한다."""
        source = io.BytesIO(image_bytes)
        reader = c2pa.Reader.try_create(mime_type, source)

        if reader is None:
            return C2paVerifyResult(has_manifest=False)

        active = reader.get_active_manifest()
        manifest_json = reader.json()
        manifest_data = json.loads(manifest_json) if manifest_json else None

        # 검증 상태 확인
        validation = reader.get_validation_results()
        errors: list[str] = []
        if validation:
            for v in validation:
                if isinstance(v, dict) and v.get("code"):
                    errors.append(v["code"])
                elif isinstance(v, str):
                    errors.append(v)

        # active manifest 에서 주요 필드 추출
        creator: str | None = None
        claim_generator: str | None = None
        asset_id: str | None = None

        if active:
            claim_generator = active.get("claim_generator")
            asset_id = active.get("title")

            # assertions에서 creator 추출
            for assertion in active.get("assertions", []):
                data = assertion.get("data", {})
                if assertion.get("label") == "stds.schema-org.CreativeWork":
                    authors = data.get("author", [])
                    if authors:
                        creator = authors[0].get("name")

        is_valid = len(errors) == 0

        return C2paVerifyResult(
            has_manifest=True,
            is_valid=is_valid,
            creator=creator,
            claim_generator=claim_generator,
            asset_id=asset_id,
            manifest_data=manifest_data,
            validation_errors=errors,
        )

    async def read_manifest(
        self,
        image_bytes: bytes,
        mime_type: str,
    ) -> C2paVerifyResult:
        """
        이미지에서 C2PA manifest를 읽고 검증한다.

        Returns:
            C2paVerifyResult (has_manifest=False 이면 manifest 없음)
        """
        try:
            return await asyncio.to_thread(
                self._read_manifest_sync, image_bytes, mime_type
            )
        except Exception:
            logger.exception("C2PA manifest read failed")
            return C2paVerifyResult(has_manifest=False)
