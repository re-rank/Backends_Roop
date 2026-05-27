"""
Steg.AI API 연동 서비스.

- 워터마크 삽입 (embed): 원본 이미지에 고유 추적 ID를 삽입
- 워터마크 검출 (detect): 의심 이미지에서 추적 ID를 추출
- API 키 미설정 시 graceful degradation
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.schemas.watermark import StegAIDetectResult, StegAIEmbedResult

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds


class StegAIService:
    """Steg.AI API 비동기 클라이언트."""

    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.enabled = bool(api_key)
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                },
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._client

    # ── 워터마크 삽입 ────────────────────────────────────────

    async def embed_watermark(
        self,
        image_bytes: bytes,
        payload: str,
        filename: str,
    ) -> StegAIEmbedResult | None:
        """
        이미지에 비가시 워터마크를 삽입한다.

        Args:
            image_bytes: 원본 이미지 바이너리
            payload: 삽입할 추적 정보 (image_id)
            filename: 파일명 (MIME 타입 추론용)

        Returns:
            StegAIEmbedResult 또는 API 미설정/실패 시 None
        """
        if not self.enabled:
            logger.warning("Steg.AI API key not configured — skipping embed")
            return None

        mime = _guess_mime(filename)
        client = await self._get_client()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await client.post(
                    "/encode",
                    files={"image": (filename, image_bytes, mime)},
                    data={"payload": payload},
                )

                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", INITIAL_BACKOFF * attempt))
                    logger.warning("Steg.AI rate limited, retrying after %.1fs", retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                response.raise_for_status()
                body = response.json()

                # 워터마크된 이미지 다운로드 (URL로 반환하는 경우)
                watermarked_bytes = image_bytes  # fallback
                if body.get("watermarked_image_url"):
                    dl_resp = await client.get(body["watermarked_image_url"])
                    dl_resp.raise_for_status()
                    watermarked_bytes = dl_resp.content
                elif body.get("watermarked_image"):
                    import base64
                    watermarked_bytes = base64.b64decode(body["watermarked_image"])

                return StegAIEmbedResult(
                    watermark_id=body.get("watermark_id", ""),
                    payload=payload,
                    watermarked_image_bytes=watermarked_bytes,
                    confidence=body.get("confidence"),
                    raw_response=body,
                )

            except httpx.TimeoutException:
                logger.warning("Steg.AI embed timeout (attempt %d/%d)", attempt, MAX_RETRIES)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(INITIAL_BACKOFF * attempt)
                    continue
                logger.error("Steg.AI embed failed after %d retries", MAX_RETRIES)
                return None

            except httpx.HTTPStatusError as exc:
                logger.error("Steg.AI embed error: %d %s", exc.response.status_code, exc.response.text[:200])
                if attempt < MAX_RETRIES and exc.response.status_code >= 500:
                    await asyncio.sleep(INITIAL_BACKOFF * attempt)
                    continue
                return None

            except Exception:
                logger.exception("Steg.AI embed unexpected error (attempt %d/%d)", attempt, MAX_RETRIES)
                return None

        return None

    # ── 워터마크 검출 ────────────────────────────────────────

    async def detect_watermark(
        self,
        image_bytes: bytes,
        filename: str,
    ) -> StegAIDetectResult:
        """
        이미지에서 워터마크를 검출한다.

        Args:
            image_bytes: 의심 이미지 바이너리
            filename: 파일명

        Returns:
            StegAIDetectResult (detected=False 포함, 미설정 시에도 반환)
        """
        if not self.enabled:
            logger.warning("Steg.AI API key not configured — skipping detect")
            return StegAIDetectResult(detected=False)

        mime = _guess_mime(filename)
        client = await self._get_client()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = await client.post(
                    "/decode",
                    files={"image": (filename, image_bytes, mime)},
                )

                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", INITIAL_BACKOFF * attempt))
                    logger.warning("Steg.AI rate limited, retrying after %.1fs", retry_after)
                    await asyncio.sleep(retry_after)
                    continue

                response.raise_for_status()
                body = response.json()

                detected = body.get("detected", False)
                return StegAIDetectResult(
                    detected=detected,
                    watermark_id=body.get("watermark_id"),
                    payload=body.get("payload"),
                    confidence=body.get("confidence"),
                    raw_response=body,
                )

            except httpx.TimeoutException:
                logger.warning("Steg.AI detect timeout (attempt %d/%d)", attempt, MAX_RETRIES)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(INITIAL_BACKOFF * attempt)
                    continue
                return StegAIDetectResult(detected=False)

            except httpx.HTTPStatusError as exc:
                logger.error("Steg.AI detect error: %d %s", exc.response.status_code, exc.response.text[:200])
                if attempt < MAX_RETRIES and exc.response.status_code >= 500:
                    await asyncio.sleep(INITIAL_BACKOFF * attempt)
                    continue
                return StegAIDetectResult(detected=False)

            except Exception:
                logger.exception("Steg.AI detect unexpected error (attempt %d/%d)", attempt, MAX_RETRIES)
                return StegAIDetectResult(detected=False)

        return StegAIDetectResult(detected=False)

    # ── 라이프사이클 ─────────────────────────────────────────

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


def _guess_mime(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "tiff": "image/tiff",
        "tif": "image/tiff",
    }.get(ext, "application/octet-stream")
