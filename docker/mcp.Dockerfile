# Multi-stage production Dockerfile for MCP Tool Gateway Layer
FROM python:3.12-slim AS runner
WORKDIR /app
RUN groupadd -g 1001 appgroup && useradd -u 1001 -g appgroup appuser
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir fastapi uvicorn pydantic httpx
COPY backend/src /app/src
ENV PYTHONPATH=/app/src
USER appuser
EXPOSE 8002
CMD ["uvicorn", "platform_api.main:app", "--host", "0.0.0.0", "--port", "8002"]
