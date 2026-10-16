# ADR-0001: Phase 0 Foundation

- Status: Accepted
- Date: 2026-09-22

## Context

The repository is a structure-only scaffold for a multi-tenant Agentic SRE, FinOps and LLMOps platform. The platform needs strong boundaries between the API, agent runtime, LLM providers, infrastructure tools, governance, and persistence before feature work begins.

## Decision

Start with a modular monolith in the existing repository layout. Establish independently testable boundaries in code first, then split processes where scaling, security, or deployment requirements justify it.

Phase 0 standardizes Python 3.12, Node.js 22, FastAPI, Next.js, PostgreSQL with pgvector, Redis, Docker Compose, and OpenTelemetry. The local stack must run without cloud or model-provider credentials.

Agents will use only the LLM Gateway and MCP Gateway interfaces. Provider SDKs and infrastructure clients will remain behind adapter boundaries. High-risk actions will be governed by centralized policy and approval services.

## Consequences

This keeps local development simple while preserving production service boundaries. Some Phase 0 containers are only infrastructure foundations; workflow, gateway, database, and integration behavior will be implemented in later phases rather than represented by false placeholder functionality.
