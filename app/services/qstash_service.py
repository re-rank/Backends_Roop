"""QStash 기반 비동기 작업 발행 서비스.

HTTP 콜백 방식으로 워커 엔드포인트를 호출하여 백그라운드 작업을 처리한다.
"""

from __future__ import annotations

import logging
from typing import Any

from qstash import AsyncQStash, Receiver

logger = logging.getLogger(__name__)


class QStashService:
    """QStash 작업 발행 + 서명 검증."""

    def __init__(
        self,
        token: str,
        current_signing_key: str,
        next_signing_key: str,
        backend_url: str,
        base_url: str = "https://qstash.upstash.io",
    ) -> None:
        self.enabled = bool(token)
        self._client: AsyncQStash | None = None
        self._receiver: Receiver | None = None
        self._backend_url = backend_url.rstrip("/")

        if self.enabled:
            self._client = AsyncQStash(token, base_url=base_url)
            if current_signing_key and next_signing_key:
                self._receiver = Receiver(
                    current_signing_key=current_signing_key,
                    next_signing_key=next_signing_key,
                )
            else:
                logger.error(
                    "QStash signing keys not configured! "
                    "Worker endpoints cannot verify request authenticity. "
                    "Set QSTASH_CURRENT_SIGNING_KEY and QSTASH_NEXT_SIGNING_KEY."
                )

    # ── 작업 발행 ───────────────────────────────
    async def publish(
        self,
        worker_path: str,
        body: dict[str, Any],
        *,
        delay: str | int | None = None,
        retries: int = 3,
    ) -> str | None:
        """워커 엔드포인트로 작업을 발행한다.

        Args:
            worker_path: 워커 경로 (예: "/api/v1/workers/protect-image")
            body: 작업 데이터 (JSON)
            delay: 지연 시간 (예: "30s", "5m" 또는 초 단위 정수)
            retries: 재시도 횟수

        Returns:
            QStash message_id 또는 None (비활성 시)
        """
        if not self.enabled:
            return None

        destination = f"{self._backend_url}{worker_path}"
        result = await self._client.message.publish_json(
            url=destination,
            body=body,
            retries=retries,
            delay=delay,
        )
        logger.info("QStash published to %s: message_id=%s", worker_path, result.message_id)
        return result.message_id

    # ── 스케줄 등록 ─────────────────────────────
    async def create_schedule(
        self,
        worker_path: str,
        body: dict[str, Any],
        cron: str,
        *,
        schedule_id: str | None = None,
    ) -> str:
        """CRON 스케줄을 등록한다.

        Args:
            worker_path: 워커 경로
            body: 작업 데이터
            cron: CRON 표현식 (예: "0 */6 * * *")
            schedule_id: 고유 스케줄 ID (중복 방지용)

        Returns:
            QStash schedule_id
        """
        if not self.enabled:
            return ""

        destination = f"{self._backend_url}{worker_path}"
        result = await self._client.schedule.create_json(
            destination=destination,
            body=body,
            cron=cron,
            schedule_id=schedule_id,
        )
        logger.info("QStash schedule created: %s (cron=%s)", result, cron)
        return result

    # ── 서명 검증 ───────────────────────────────
    def verify_signature(self, *, signature: str, body: str, url: str | None = None) -> bool:
        """QStash 요청의 서명을 검증한다.

        Returns:
            True: 유효한 서명, False: 검증 실패 또는 Receiver 미설정
        """
        if not self._receiver:
            logger.error("QStash Receiver not configured — rejecting request")
            return False

        try:
            self._receiver.verify(
                signature=signature,
                body=body,
                url=url,
            )
            return True
        except Exception:
            logger.warning("QStash signature verification failed")
            return False
