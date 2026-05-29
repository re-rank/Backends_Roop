import asyncio
import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.services.analysis_service import AnalysisService
from app.services.c2pa_service import C2paService
from app.services.embedding_service import EmbeddingService
from app.services.feature_match_service import FeatureMatchService
from app.services.phash_service import PHashService
from app.services.evidence_capture_service import EvidenceCaptureService
from app.services.file_storage_service import FileStorageService
from app.services.qstash_service import QStashService
from app.services.redis_service import RedisService
from app.services.stegai_service import StegAIService
from app.services.vector_search_service import VectorSearchService

logger = logging.getLogger(__name__)


# ── Sentry ──
_SENTRY_SENSITIVE_KEYS = {
    "DATABASE_URL", "APP_SECRET_KEY", "MONGODB_URI",
    "STEGAI_API_KEY", "QSTASH_TOKEN", "UPSTASH_REDIS_TOKEN",
    "QSTASH_CURRENT_SIGNING_KEY", "QSTASH_NEXT_SIGNING_KEY",
}


def _scrub_sentry_event(event: dict, hint: dict) -> dict:
    """Sentry 전송 전 민감 정보 제거."""
    if "extra" in event:
        for key in _SENTRY_SENSITIVE_KEYS:
            event["extra"].pop(key, None)
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        if isinstance(headers, dict):
            headers.pop("authorization", None)
            headers.pop("upstash-signature", None)
    return event


if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,
        environment=settings.ENVIRONMENT,
        before_send=_scrub_sentry_event,
    )
    logger.info("Sentry initialized (env=%s)", settings.ENVIRONMENT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── 시작 시 초기화 ──
    app.state.stegai = StegAIService(
        api_key=settings.STEGAI_API_KEY,
        base_url=settings.STEGAI_BASE_URL,
    )
    app.state.c2pa = C2paService(
        cert_path=settings.C2PA_CERT_PATH,
        key_path=settings.C2PA_KEY_PATH,
    )

    # 분석 엔진
    phash_svc = PHashService()

    embedding_svc = EmbeddingService()
    if settings.ENABLE_EMBEDDING_MODELS:
        await asyncio.to_thread(embedding_svc.load_models)

    vector_search_svc = VectorSearchService(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )
    vector_search_svc.ensure_collections()

    feature_match_svc = FeatureMatchService()

    app.state.analysis = AnalysisService(
        phash_svc=phash_svc,
        embedding_svc=embedding_svc,
        vector_search_svc=vector_search_svc,
        feature_match_svc=feature_match_svc,
    )

    # 증거 캡처
    evidence_svc = EvidenceCaptureService()
    await evidence_svc.check_browser()
    app.state.evidence_capture = evidence_svc

    # MongoDB 파일 스토리지
    file_storage = FileStorageService(
        uri=settings.MONGODB_URI,
        db_name=settings.MONGODB_DB_NAME,
    )
    app.state.file_storage = file_storage

    # QStash + Redis
    app.state.qstash = QStashService(
        token=settings.QSTASH_TOKEN,
        current_signing_key=settings.QSTASH_CURRENT_SIGNING_KEY,
        next_signing_key=settings.QSTASH_NEXT_SIGNING_KEY,
        backend_url=settings.BACKEND_URL,
        base_url=settings.QSTASH_URL,
    )
    app.state.redis = RedisService(
        url=settings.UPSTASH_REDIS_URL,
        token=settings.UPSTASH_REDIS_TOKEN,
    )

    yield

    # ── 종료 시 정리 ──
    await app.state.stegai.close()
    await file_storage.close()
    vector_search_svc.close()


app = FastAPI(
    title="Re-Proof API",
    description="이미지 권리보호 SaaS 백엔드",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"success": False, "detail": "Internal server error"},
    )


@app.get("/health")
async def health_check():
    """서비스 헬스체크. Railway 헬스체크용 — 상세 정보는 노출하지 않음."""
    checks: dict[str, bool] = {}

    # PostgreSQL
    try:
        from app.core.database import engine

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False

    # MongoDB
    try:
        storage: FileStorageService = app.state.file_storage
        checks["mongodb"] = await storage.ping()
    except Exception:
        checks["mongodb"] = False

    # Qdrant
    try:
        vector_svc: VectorSearchService = app.state.analysis.vector_search
        checks["qdrant"] = vector_svc.is_healthy()
    except Exception:
        checks["qdrant"] = False

    # Upstash Redis
    try:
        redis_svc: RedisService = app.state.redis
        checks["redis"] = redis_svc.enabled
    except Exception:
        checks["redis"] = False

    all_healthy = all(checks.values())
    status = "healthy" if all_healthy else "degraded"

    # 프로덕션에서는 개별 서비스 상태를 노출하지 않음
    if settings.ENVIRONMENT == "production":
        return {"status": status}

    return {"status": status, "checks": checks}
