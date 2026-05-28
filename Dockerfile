FROM python:3.12-slim

WORKDIR /app

# 비root 사용자 생성
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

# 시스템 의존성 (OpenCV, Playwright)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 (torch CPU only로 이미지 크기 절약)
COPY requirements.txt .
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치 (root로 설치 후 사용자 전환)
RUN playwright install chromium && playwright install-deps chromium

# 앱 코드
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY certs/ ./certs/
COPY start.sh .

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
