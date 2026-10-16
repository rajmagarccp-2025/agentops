FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/pyproject.toml backend/requirements-dev.txt ./backend/
COPY backend/src ./backend/src
RUN pip install --no-cache-dir ./backend
RUN useradd --create-home --uid 10001 appuser
USER 10001
EXPOSE 8000
CMD ["uvicorn", "platform_api.main:app", "--app-dir", "backend/src", "--host", "0.0.0.0", "--port", "8000"]
