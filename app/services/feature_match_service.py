"""ORB 피처 매칭 서비스 (OpenCV).

원본-의심 이미지 간 특징점 매칭으로 시각적 증거 이미지를 생성한다.
"""

from __future__ import annotations

import asyncio
import io
import logging

import cv2
import numpy as np
from PIL import Image

from app.schemas.analysis import FeatureMatchResult

logger = logging.getLogger(__name__)


class FeatureMatchService:
    """ORB 기반 특징점 매칭 및 시각화 서비스."""

    N_FEATURES = 1000
    GOOD_DISTANCE_THRESHOLD = 50

    @staticmethod
    def _bytes_to_cv2(image_bytes: bytes) -> np.ndarray:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    def match_features_sync(
        self,
        original_bytes: bytes,
        suspect_bytes: bytes,
    ) -> FeatureMatchResult:
        """동기: ORB 특징점 매칭 + 시각화 이미지 생성."""
        original = self._bytes_to_cv2(original_bytes)
        suspect = self._bytes_to_cv2(suspect_bytes)

        gray1 = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(suspect, cv2.COLOR_BGR2GRAY)

        orb = cv2.ORB_create(nfeatures=self.N_FEATURES)
        kp1, des1 = orb.detectAndCompute(gray1, None)
        kp2, des2 = orb.detectAndCompute(gray2, None)

        if des1 is None or des2 is None:
            return FeatureMatchResult()

        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = sorted(bf.match(des1, des2), key=lambda m: m.distance)

        good = [m for m in matches if m.distance < self.GOOD_DISTANCE_THRESHOLD]

        # 매칭 시각화 이미지 생성
        vis = cv2.drawMatches(
            original,
            kp1,
            suspect,
            kp2,
            matches[:50],
            None,
            flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
        )
        _, png = cv2.imencode(".png", vis)

        return FeatureMatchResult(
            num_matches=len(matches),
            good_matches=len(good),
            match_visualization_bytes=png.tobytes(),
        )

    async def match_features(
        self,
        original_bytes: bytes,
        suspect_bytes: bytes,
    ) -> FeatureMatchResult:
        """비동기: ORB 피처 매칭. 빈 바이트 시 빈 결과."""
        if not original_bytes or not suspect_bytes:
            return FeatureMatchResult()
        try:
            return await asyncio.to_thread(
                self.match_features_sync, original_bytes, suspect_bytes
            )
        except Exception:
            logger.exception("Feature matching failed")
            return FeatureMatchResult()
