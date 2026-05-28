"""비교 이미지 생성 서비스.

원본-의심 이미지의 side-by-side 배치 및 diff heatmap 시각화.
"""

from __future__ import annotations

import asyncio
import io
import logging

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.schemas.evidence import ComparisonResult

logger = logging.getLogger(__name__)

TARGET_HEIGHT = 600  # 비교 이미지 높이 통일


class ComparisonService:
    """원본-의심 이미지 비교 시각화 서비스."""

    # ── Side-by-side ─────────────────────────────────

    @staticmethod
    def _create_side_by_side_sync(
        original_bytes: bytes,
        suspect_bytes: bytes,
        label_original: str = "Original",
        label_suspect: str = "Suspect",
    ) -> bytes:
        """원본과 의심 이미지를 나란히 배치한 비교 이미지 생성."""
        orig = Image.open(io.BytesIO(original_bytes)).convert("RGB")
        susp = Image.open(io.BytesIO(suspect_bytes)).convert("RGB")

        # 동일 높이로 리사이즈
        h = TARGET_HEIGHT
        orig_w = int(orig.width * h / orig.height)
        susp_w = int(susp.width * h / susp.height)
        orig = orig.resize((orig_w, h), Image.LANCZOS)
        susp = susp.resize((susp_w, h), Image.LANCZOS)

        # 라벨 영역 (상단 40px)
        label_h = 40
        gap = 20
        total_w = orig_w + gap + susp_w
        total_h = h + label_h

        canvas = Image.new("RGB", (total_w, total_h), color=(255, 255, 255))
        draw = ImageDraw.Draw(canvas)

        # 라벨 텍스트
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except OSError:
            font = ImageFont.load_default()

        draw.text((orig_w // 2 - 30, 8), label_original, fill=(0, 0, 0), font=font)
        draw.text((orig_w + gap + susp_w // 2 - 30, 8), label_suspect, fill=(255, 0, 0), font=font)

        # 이미지 배치
        canvas.paste(orig, (0, label_h))
        canvas.paste(susp, (orig_w + gap, label_h))

        buf = io.BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue()

    # ── Diff overlay (heatmap) ───────────────────────

    @staticmethod
    def _create_diff_overlay_sync(
        original_bytes: bytes,
        suspect_bytes: bytes,
    ) -> bytes:
        """원본-의심 이미지 차이점을 히트맵으로 시각화."""
        orig = Image.open(io.BytesIO(original_bytes)).convert("RGB")
        susp = Image.open(io.BytesIO(suspect_bytes)).convert("RGB")

        # 동일 크기로 리사이즈 (원본 기준)
        size = (min(orig.width, 800), min(orig.height, 800))
        orig = orig.resize(size, Image.LANCZOS)
        susp = susp.resize(size, Image.LANCZOS)

        orig_np = np.array(orig)
        susp_np = np.array(susp)

        # 차이 계산 → 히트맵
        diff = cv2.absdiff(orig_np, susp_np)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_RGB2GRAY)
        heatmap = cv2.applyColorMap(gray_diff, cv2.COLORMAP_JET)

        # 원본 위에 히트맵 오버레이 (50% 투명도)
        orig_bgr = cv2.cvtColor(orig_np, cv2.COLOR_RGB2BGR)
        overlay = cv2.addWeighted(orig_bgr, 0.5, heatmap, 0.5, 0)

        _, png = cv2.imencode(".png", overlay)
        return png.tobytes()

    # ── 비동기 ────────────────────────────────────────

    async def create_comparison(
        self,
        original_bytes: bytes,
        suspect_bytes: bytes,
    ) -> ComparisonResult:
        """비교 이미지 생성 (side-by-side + diff overlay).

        빈 바이트 시 빈 결과.
        """
        if not original_bytes or not suspect_bytes:
            return ComparisonResult()

        try:
            sbs = await asyncio.to_thread(
                self._create_side_by_side_sync, original_bytes, suspect_bytes
            )
            diff = await asyncio.to_thread(
                self._create_diff_overlay_sync, original_bytes, suspect_bytes
            )
            return ComparisonResult(
                side_by_side_bytes=sbs,
                diff_overlay_bytes=diff,
            )
        except Exception:
            logger.exception("Comparison image generation failed")
            return ComparisonResult()
