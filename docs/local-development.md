# Local Development Guide

## Prerequisites

- Python 3.12+
- Node.js 22+ & npm 10+
- Docker & Docker Compose
- Make / PowerShell

## Quickstart

Start the entire platform locally with Docker Compose:

```bash
docker compose up --build
```

Access services:
- **Web Platform**: `http://localhost:3000`
- **FastAPI API**: `http://localhost:8000`
- **OpenAPI Swagger Docs**: `http://localhost:8000/docs`
- **PostgreSQL**: `localhost:5432`
- **Redis**: `localhost:6379`

## Local Python Testing

```bash
.\.venv\Scripts\python.exe -m pytest
```

## Local Frontend Typechecking

```bash
cd frontend
node ./node_modules/typescript/lib/tsc.js --noEmit
```
