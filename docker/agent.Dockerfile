# Multi-stage production Dockerfile for Agent Orchestrator Runtime
FROM python:3.12-slim AS runner
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
RUN groupadd -g 1001 appgroup && useradd -u 1001 -g appgroup appuser
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir fastapi uvicorn pydantic langgraph langchain-core httpx
COPY backend/src /app/src
ENV PYTHONPATH=/app/src
USER appuser
EXPOSE 8001
CMD ["uvicorn", "platform_api.main:app", "--host", "0.0.0.0", "--port", "8001"]
