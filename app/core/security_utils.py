"""보안 유틸리티 함수 모음.

MIME 검증, SSRF 방어, 파일 업로드 보호 등 공통 보안 로직.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import UploadFile

from app.core.exceptions import BadRequestError

MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB

# ── MIME 매직 바이트 검증 ────────────────────────────

# (시그니처, MIME 타입)
_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
]

# WebP: "RIFF" + 4바이트 크기 + "WEBP"
_WEBP_RIFF = b"RIFF"
_WEBP_MARKER = b"WEBP"


def verify_image_magic_bytes(content: bytes) -> bool:
    """파일 시그니처(매직 바이트)로 실제 이미지인지 검증한다.

    지원: JPEG, PNG, WebP
    """
    if len(content) < 12:
        return False

    for sig, _ in _MAGIC_SIGNATURES:
        if content.startswith(sig):
            return True

    # WebP: RIFF[4 bytes]WEBP
    if content[:4] == _WEBP_RIFF and content[8:12] == _WEBP_MARKER:
        return True

    return False


# ── SSRF 방어 ────────────────────────────────────────

_BLOCKED_HOSTS = frozenset({
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "metadata.google.internal",
    "169.254.169.254",
})


def is_ssrf_safe_url(url: str) -> bool:
    """캡처/다운로드 URL의 SSRF 안전성을 검증한다.

    DNS 조회 후 실제 IP가 내부 네트워크인지까지 확인한다.
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False

        hostname = parsed.hostname or ""
        if not hostname:
            return False

        if hostname.lower() in _BLOCKED_HOSTS:
            return False

        # 직접 IP 입력 시 즉시 검증
        try:
            addr = ipaddress.ip_address(hostname)
            if _is_dangerous_ip(addr):
                return False
            return True
        except ValueError:
            pass  # 도메인명 — DNS 조회 필요

        # DNS 조회 후 리졸브된 IP 검증
        try:
            addrs = socket.getaddrinfo(hostname, None)
            for addrinfo in addrs:
                addr = ipaddress.ip_address(addrinfo[4][0])
                if _is_dangerous_ip(addr):
                    return False
        except socket.gaierror:
            return False  # DNS 조회 실패 시 차단

        return True
    except Exception:
        return False


def _is_dangerous_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """내부/위험 IP 여부 확인."""
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
    )


# ── 파일 업로드 보호 ─────────────────────────────────


async def read_upload_safely(
    file: UploadFile,
    *,
    max_size: int = MAX_UPLOAD_SIZE,
    verify_image: bool = True,
) -> bytes:
    """업로드 파일을 스트리밍으로 읽으며 크기 제한을 적용한다.

    메모리 보호: max_size 초과 시 즉시 중단하여 OOM 방지.
    verify_image=True이면 매직 바이트도 검증.

    Returns:
        파일 바이트
    Raises:
        BadRequestError: 크기 초과 또는 유효하지 않은 이미지
    """
    chunks: list[bytes] = []
    total = 0

    while True:
        chunk = await file.read(64 * 1024)  # 64KB chunks
        if not chunk:
            break
        total += len(chunk)
        if total > max_size:
            raise BadRequestError(f"File size exceeds {max_size // (1024 * 1024)}MB limit")
        chunks.append(chunk)

    content = b"".join(chunks)

    if verify_image and not verify_image_magic_bytes(content):
        raise BadRequestError("File content does not match a valid image format")

    return content
