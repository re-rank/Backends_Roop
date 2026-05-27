"""Playwright 기반 웹 캡처 및 이미지 다운로드 서비스.

Playwright/chromium 미설치 시 graceful degradation (enabled=False).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import httpx

from app.schemas.evidence import DownloadedImage, PageCaptureResult

logger = logging.getLogger(__name__)

# Playwright가 없을 수 있으므로 lazy import
_playwright_available = False
try:
    from playwright.async_api import async_playwright

    _playwright_available = True
except ImportError:
    pass


class EvidenceCaptureService:
    """웹 페이지 캡처 + 이미지 다운로드 서비스."""

    VIEWPORT = {"width": 1920, "height": 1080}
    PAGE_TIMEOUT_MS = 30_000
    IMAGE_DOWNLOAD_TIMEOUT = 15.0
    MAX_IMAGES_PER_PAGE = 50

    def __init__(self) -> None:
        self.enabled = _playwright_available
        if not self.enabled:
            logger.warning(
                "Playwright not available — evidence capture disabled"
            )

    async def check_browser(self) -> bool:
        """chromium 바이너리가 설치되어 있는지 확인."""
        if not _playwright_available:
            return False
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                await browser.close()
            return True
        except Exception:
            logger.warning("Chromium browser not installed — evidence capture disabled")
            self.enabled = False
            return False

    # ── 페이지 캡처 ──────────────────────────────────

    async def capture_page(self, url: str) -> PageCaptureResult | None:
        """URL 페이지를 캡처하여 스크린샷, HTML, 이미지 URL 추출.

        Returns:
            PageCaptureResult 또는 실패 시 None
        """
        if not self.enabled:
            logger.warning("Evidence capture disabled — skipping page capture")
            return None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport=self.VIEWPORT,
                    locale="ko-KR",
                )
                page = await context.new_page()

                await page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=self.PAGE_TIMEOUT_MS,
                )

                # 1. 전체 페이지 스크린샷
                screenshot = await page.screenshot(
                    full_page=True, type="png"
                )

                # 2. HTML 스냅샷
                html_content = await page.content()

                # 3. 이미지 URL 추출
                image_urls: list[str] = await page.evaluate(
                    """() => Array.from(document.querySelectorAll('img'))
                        .map(img => img.src)
                        .filter(src => src.startsWith('http'))"""
                )

                # 4. 메타 정보
                title = await page.title()
                final_url = page.url

                await browser.close()

                return PageCaptureResult(
                    screenshot_bytes=screenshot,
                    html_content=html_content,
                    image_urls=image_urls[: self.MAX_IMAGES_PER_PAGE],
                    page_title=title,
                    final_url=final_url,
                    captured_at=datetime.now(timezone.utc),
                )
        except Exception:
            logger.exception("Page capture failed for URL: %s", url)
            return None

    # ── 이미지 다운로드 ──────────────────────────────

    async def download_images(
        self, image_urls: list[str]
    ) -> list[DownloadedImage]:
        """URL 목록에서 이미지를 다운로드. 실패한 URL은 건너뛴다."""
        results: list[DownloadedImage] = []

        async with httpx.AsyncClient(
            timeout=self.IMAGE_DOWNLOAD_TIMEOUT,
            follow_redirects=True,
        ) as client:
            for url in image_urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        continue

                    content_type = resp.headers.get("content-type", "")
                    if "image" not in content_type:
                        continue

                    sha256 = hashlib.sha256(resp.content).hexdigest()
                    results.append(
                        DownloadedImage(
                            url=url,
                            image_bytes=resp.content,
                            mime_type=content_type.split(";")[0].strip(),
                            sha256_hash=sha256,
                        )
                    )
                except httpx.RequestError:
                    continue

        logger.info(
            "Downloaded %d/%d images", len(results), len(image_urls)
        )
        return results
