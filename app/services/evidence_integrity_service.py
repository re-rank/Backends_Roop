"""증거 무결성 보장 서비스.

SHA-256 해시 + Merkle root로 증거 체인의 무결성을 증명한다.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone


class EvidenceIntegrityService:
    """증거 파일 해싱 및 Merkle root 생성."""

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        """SHA-256 해시 생성."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def compute_merkle_root(hashes: list[str]) -> str:
        """해시 목록에서 Merkle root를 계산한다.

        빈 목록 시 빈 문자열, 단일 해시 시 그대로 반환.
        """
        if not hashes:
            return ""
        if len(hashes) == 1:
            return hashes[0]

        # 이진 트리 방식으로 반복 해싱
        current = list(hashes)
        while len(current) > 1:
            next_level: list[str] = []
            for i in range(0, len(current), 2):
                left = current[i]
                right = current[i + 1] if i + 1 < len(current) else left
                combined = hashlib.sha256(
                    (left + right).encode()
                ).hexdigest()
                next_level.append(combined)
            current = next_level

        return current[0]

    def create_evidence_chain(
        self, hashes: list[str]
    ) -> dict:
        """증거 체인 요약 생성.

        Returns:
            {evidence_count, hashes, merkle_root, created_at}
        """
        return {
            "evidence_count": len(hashes),
            "hashes": hashes,
            "merkle_root": self.compute_merkle_root(hashes),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
