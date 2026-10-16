# Production Dockerfile for Background Async Worker
FROM python:3.12-slim AS builder

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/requirements-dev.txt ./
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 10001 appgroup && useradd -u 10001 -g appgroup -s /sbin/nologin appuser

COPY --from=builder /install /usr/local
COPY backend/src /app/src

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER 10001:10001

CMD ["python", "-m", "platform_api.worker"]

