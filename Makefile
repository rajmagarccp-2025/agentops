SHELL := pwsh.exe
.SHELLFLAGS := -NoProfile -Command

PYTHON ?= python
COMPOSE ?= docker compose

.PHONY: help setup dev test lint format typecheck migrate seed docker-build docker-up docker-down integration-test e2e clean

help:
	@Write-Output "Available targets: setup dev test lint format typecheck migrate seed docker-build docker-up docker-down integration-test e2e clean"

setup:
	$(PYTHON) -m venv .venv
	.venv\Scripts\python.exe -m pip install --upgrade pip
	.venv\Scripts\python.exe -m pip install -e backend\[dev\]
	Set-Location frontend; npm install

dev:
	$(COMPOSE) up --build

test:
	.venv\Scripts\python.exe -m pytest

lint:
	.venv\Scripts\python.exe -m ruff check backend/src backend/tests

format:
	.venv\Scripts\python.exe -m ruff format backend/src backend/tests

typecheck:
	.venv\Scripts\python.exe -m mypy backend/src
	Set-Location frontend; npm run typecheck

migrate:
	Set-Location backend; ..\.venv\Scripts\python.exe -m alembic -c alembic.ini upgrade head

seed:
	.venv\Scripts\python.exe scripts\seed\demo_seed.py

docker-build:
	$(COMPOSE) build

docker-up:
	$(COMPOSE) up --build -d

docker-down:
	$(COMPOSE) down

terraform-init:
	Set-Location infrastructure/terraform/environments/dev; terraform init

terraform-plan:
	Set-Location infrastructure/terraform/environments/dev; terraform plan

helm-lint:
	helm lint deployment/helm/platform

helm-template:
	helm template platform deployment/helm/platform --values deployment/helm/platform/values-gcp.yaml

security-scan:
	.venv\Scripts\python.exe -m bandit -r backend/src

integration-test:
	.venv\Scripts\python.exe -m pytest backend/tests -q

integration-test-db:
	$(COMPOSE) up -d postgres redis
	.venv\Scripts\python.exe -m pytest backend/tests/integration -m integration -q

e2e:
	Set-Location frontend; node ./node_modules/typescript/lib/tsc.js --noEmit

clean:
	if (Test-Path .venv) { Remove-Item -Recurse -Force .venv }
	if (Test-Path frontend\node_modules) { Remove-Item -Recurse -Force frontend\node_modules }
	if (Test-Path frontend\.next) { Remove-Item -Recurse -Force frontend\.next }

