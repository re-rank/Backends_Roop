"""CLIP + DINOv2 이미지 임베딩 서비스.

모델 로딩이 무거우므로 lifespan에서 1회 호출하고 싱글톤으로 유지.
torch가 없거나 모델 다운로드 실패 시 graceful degradation (enabled=False).
"""

from __future__ import annotations

import asyncio
import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)


class EmbeddingService:
    """CLIP ViT-B-32 (512d) + DINOv2-base (768d) 임베딩 생성."""

    CLIP_DIM = 512
    DINO_DIM = 768

    def __init__(self) -> None:
        self._clip_model = None
        self._clip_preprocess = None
        self._dino_model = None
        self._dino_processor = None
        self.enabled = False

    # ── 모델 로드 (lifespan에서 호출) ─────────────────

    def load_models(self) -> None:
        """CLIP + DINOv2 모델 로드. 실패 시 enabled=False."""
        try:
            import open_clip
            import torch  # noqa: F401

            self._clip_model, _, self._clip_preprocess = (
                open_clip.create_model_and_transforms(
                    "ViT-B-32", pretrained="openai"
                )
            )
            self._clip_model.eval()
            logger.info("CLIP ViT-B-32 loaded")

            from transformers import AutoImageProcessor, AutoModel

            self._dino_processor = AutoImageProcessor.from_pretrained(
                "facebook/dinov2-base"
            )
            self._dino_model = AutoModel.from_pretrained("facebook/dinov2-base")
            self._dino_model.eval()
            logger.info("DINOv2-base loaded")

            self.enabled = True
        except Exception:
            logger.exception(
                "Embedding model loading failed — embedding disabled"
            )
            self.enabled = False

    # ── 동기 (to_thread용) ────────────────────────────

    def _get_clip_embedding_sync(self, image_bytes: bytes) -> list[float]:
        import torch

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        tensor = self._clip_preprocess(img).unsqueeze(0)
        with torch.no_grad():
            emb = self._clip_model.encode_image(tensor)
            emb = emb / emb.norm(dim=-1, keepdim=True)
        return emb.squeeze().tolist()

    def _get_dino_embedding_sync(self, image_bytes: bytes) -> list[float]:
        import torch

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        inputs = self._dino_processor(images=img, return_tensors="pt")
        with torch.no_grad():
            outputs = self._dino_model(**inputs)
            emb = outputs.last_hidden_state[:, 0]  # CLS token
            emb = emb / emb.norm(dim=-1, keepdim=True)
        return emb.squeeze().tolist()

    # ── 비동기 ────────────────────────────────────────

    async def get_clip_embedding(self, image_bytes: bytes) -> list[float] | None:
        """CLIP 임베딩 생성. 미활성 시 None."""
        if not self.enabled or not image_bytes:
            return None
        try:
            return await asyncio.to_thread(
                self._get_clip_embedding_sync, image_bytes
            )
        except Exception:
            logger.exception("CLIP embedding failed")
            return None

    async def get_dino_embedding(self, image_bytes: bytes) -> list[float] | None:
        """DINOv2 임베딩 생성. 미활성 시 None."""
        if not self.enabled or not image_bytes:
            return None
        try:
            return await asyncio.to_thread(
                self._get_dino_embedding_sync, image_bytes
            )
        except Exception:
            logger.exception("DINOv2 embedding failed")
            return None
