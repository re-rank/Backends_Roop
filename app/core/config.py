from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Neon PostgreSQL (필수 — .env 또는 환경변수에서 반드시 설정)
    DATABASE_URL: str

    # Steg.AI
    STEGAI_API_KEY: str = ""
    STEGAI_BASE_URL: str = "https://api.steg.ai/v1"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""

    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "reproof"

    # Redis / QStash
    UPSTASH_REDIS_URL: str = ""
    UPSTASH_REDIS_TOKEN: str = ""
    QSTASH_TOKEN: str = ""
    QSTASH_URL: str = "https://qstash.upstash.io"
    QSTASH_CURRENT_SIGNING_KEY: str = ""
    QSTASH_NEXT_SIGNING_KEY: str = ""

    # C2PA
    C2PA_CERT_PATH: str = "certs/reproof-dev-chain.pem"
    C2PA_KEY_PATH: str = "certs/reproof-dev-pkcs8.key"

    # 분석 엔진
    ENABLE_EMBEDDING_MODELS: bool = True  # False면 CLIP/DINOv2 로딩 skip
    ANALYSIS_PHASH_THRESHOLD: float = 0.80
    ANALYSIS_VECTOR_THRESHOLD: float = 0.50

    # 모니터링
    SENTRY_DSN: str = ""
    ENVIRONMENT: str = "development"

    # 앱 설정
    APP_SECRET_KEY: str  # 필수 — .env 또는 환경변수에서 반드시 설정
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    ALLOW_DIRECT_WORKER_CALLS: bool = False  # True: QStash 없이 워커 직접 호출 허용 (개발용)


settings = Settings()
