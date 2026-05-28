"""pHash(Perceptual Hash) 생성 및 비교 서비스."""

from __future__ import annotations

import asyncio
import io
import logging

import imagehash
from PIL import Image

logger = logging.getLogger(__name__)


class PHashService:
    """pHash 생성·비교 서비스.

    hash_size=8 → 64-bit hash → 16 hex chars.
    DB의 BIT(64) 컬럼과 일치.
    """

    HASH_SIZE = 8  # 8×8 = 64-bit

    # ── 동기 ──────────────────────────────────────────

    def generate_phash_sync(self, image_bytes: bytes) -> str:
        """이미지 바이트 → pHash hex string."""
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return str(imagehash.phash(img, hash_size=self.HASH_SIZE))

    @staticmethod
    def compare_phash(hash1: str, hash2: str) -> float:
        """두 pHash 간 유사도 (0.0 ~ 1.0, 1.0 = 동일)."""
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        max_distance = h1.hash.size  # total bits (64)
        distance = h1 - h2  # hamming distance
        return 1.0 - (distance / max_distance)

    @staticmethod
    def phash_hex_to_bits(hex_str: str) -> str:
        """hex string → '0'/'1' 64자리 binary string (BIT(64) 컬럼용)."""
        return bin(int(hex_str, 16))[2:].zfill(64)

    # ── 비동기 ────────────────────────────────────────

    async def generate_phash(self, image_bytes: bytes) -> str | None:
        """비동기: pHash 생성. 빈 바이트 또는 실패 시 None."""
        if not image_bytes:
            return None
        try:
            return await asyncio.to_thread(self.generate_phash_sync, image_bytes)
        except Exception:
            logger.exception("pHash generation failed")
            return None
