"""Advisory lock을 사용하는 안전한 마이그레이션 러너.

여러 인스턴스가 동시에 배포되어도 한 번만 마이그레이션이 실행된다.
PostgreSQL pg_advisory_lock(lock_id) → alembic upgrade head → 해제.
"""

import subprocess
import sys

import psycopg2

from app.core.config import settings

# advisory lock ID (임의 고정 정수)
MIGRATION_LOCK_ID = 839271


def run() -> None:
    # asyncpg URL → psycopg2 URL 변환
    sync_url = settings.DATABASE_URL.replace(
        "postgresql+asyncpg://", "postgresql://"
    )

    conn = psycopg2.connect(sync_url)
    conn.autocommit = True
    cur = conn.cursor()

    try:
        # advisory lock 획득 시도 (non-blocking)
        cur.execute("SELECT pg_try_advisory_lock(%s)", (MIGRATION_LOCK_ID,))
        acquired = cur.fetchone()[0]

        if not acquired:
            print("Migration lock held by another instance — skipping")
            return

        print("Migration lock acquired — running alembic upgrade head")
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            sys.exit(result.returncode)

        print("Migration completed successfully")
    finally:
        cur.execute("SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_ID,))
        cur.close()
        conn.close()


if __name__ == "__main__":
    run()
