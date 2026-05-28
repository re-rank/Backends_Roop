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
    # ── 시작 시 초기화 (각 서비스 실패 시 degraded 모드로 계속) ──
    try:
        app.state.stegai = StegAIService(
            api_key=settings.STEGAI_API_KEY,
            base_url=settings.STEGAI_BASE_URL,
        )
    except Exception:
        app.state.stegai = None
        logger.warning("StegAI service unavailable — skipping")

    try:
        app.state.c2pa = C2paService(
            cert_path=settings.C2PA_CERT_PATH,
            key_path=settings.C2PA_KEY_PATH,
        )
    except Exception:
        app.state.c2pa = None
        logger.warning("C2PA service unavailable — skipping")

    # 분석 엔진
    phash_svc = PHashService()

    embedding_svc = EmbeddingService()
    if settings.ENABLE_EMBEDDING_MODELS:
        try:
            await asyncio.to_thread(embedding_svc.load_models)
        except Exception:
            logger.warning("Embedding models failed to load — skipping")

    vector_search_svc = None
    if "localhost" not in settings.QDRANT_URL:
        try:
            vector_search_svc = VectorSearchService(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
            )
            vector_search_svc.ensure_collections()
        except Exception:
            vector_search_svc = None
            logger.warning("Qdrant unavailable — vector search disabled")
    else:
        logger.info("Qdrant URL is localhost — skipping (not available in production)")

    feature_match_svc = FeatureMatchService()

    app.state.analysis = AnalysisService(
        phash_svc=phash_svc,
        embedding_svc=embedding_svc,
        vector_search_svc=vector_search_svc,
        feature_match_svc=feature_match_svc,
    )

    # 증거 캡처
    try:
        evidence_svc = EvidenceCaptureService()
        await evidence_svc.check_browser()
        app.state.evidence_capture = evidence_svc
    except Exception:
        app.state.evidence_capture = None
        logger.warning("Evidence capture service unavailable — skipping")

    # MongoDB 파일 스토리지
    file_storage = None
    if "localhost" not in settings.MONGODB_URI:
        try:
            file_storage = FileStorageService(
                uri=settings.MONGODB_URI,
                db_name=settings.MONGODB_DB_NAME,
            )
            app.state.file_storage = file_storage
        except Exception:
            app.state.file_storage = None
            logger.warning("MongoDB unavailable — file storage disabled")
    else:
        app.state.file_storage = None
        logger.info("MongoDB URI is localhost — skipping (not available in production)")

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

    logger.info("App startup complete (degraded services logged above)")

    yield

    # ── 종료 시 정리 ──
    if app.state.stegai:
        await app.state.stegai.close()
    if file_storage:
        await file_storage.close()
    if vector_search_svc:
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
        storage = getattr(app.state, "file_storage", None)
        checks["mongodb"] = await storage.ping() if storage else False
    except Exception:
        checks["mongodb"] = False

    # Qdrant
    try:
        analysis = getattr(app.state, "analysis", None)
        vector_svc = getattr(analysis, "vector_search", None) if analysis else None
        checks["qdrant"] = vector_svc.is_healthy() if vector_svc else False
    except Exception:
        checks["qdrant"] = False

    # Upstash Redis
    try:
        redis_svc = getattr(app.state, "redis", None)
        checks["redis"] = redis_svc.enabled if redis_svc else False
    except Exception:
        checks["redis"] = False

    # DB만 정상이면 서비스 가능
    status = "healthy" if checks.get("database") else "degraded"

    # 프로덕션에서는 개별 서비스 상태를 노출하지 않음
    if settings.ENVIRONMENT == "production":
        return {"status": status}

    return {"status": status, "checks": checks}
