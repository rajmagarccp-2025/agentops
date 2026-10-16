# Frontend

The operations console is a Next.js 15 App Router application using React 19 and TypeScript.

## Local development

1. Start the FastAPI service from `backend` (see [backend/README.md](../backend/README.md)).
2. Copy `.env.example` to `.env.local` and set the API URLs reachable from the browser and the Next.js server. The proxy defaults to `http://127.0.0.1:8000/api/v1` in development and `http://api:8000/api/v1` in production.
3. Install frontend dependencies with `npm install`, then run `npm run dev`.

The app router pages live under `src/app`. Authenticated requests go through `src/app/api/proxy/[...path]`; the Next.js server forwards the HttpOnly access-token cookie as a bearer token and forwards workspace scope headers. Do not put credentials in `NEXT_PUBLIC_*` variables.

## Application flow

Users authenticate, select an organization, project, and environment, then navigate operational features from the shared navigation. The workspace context switch updates the authenticated server context before dependent data is loaded. Authorization controls navigation and mutation affordances, while the API remains authoritative for access decisions.

The shared workspace switcher keeps the active organization → project → environment and effective role visible throughout the console. Pages use the existing App Router structure; the selected hierarchy is synchronized as authenticated API context rather than duplicated in route segments. After authentication, users with no organization go to onboarding, while invited users return to the invitation they were sent.

Navigation uses the backend's Organization → Project → Environment hierarchy. There is no separate Application entity in the current API: application workloads appear in Infrastructure resources, while Agents are operational workflows scoped to the selected project and environment. The Agent runs route opens the existing runs tab; Knowledge and Observability shortcuts lead to sections on their real feature pages. Logs and traces remain visibly unavailable until a query backend exists.

The overview uses live health, incident, cost, change, knowledge, LLM telemetry, approval, and agent-run APIs. Incident, cost, and inventory APIs are organization-scoped; the page labels this scope rather than implying those signals are environment-specific. Agent activity is filtered to the selected project and environment.

The Agents page exposes the backend-supported workflow catalog, permission-aware run controls, run results, and recent execution history. Run history is read from the current LangGraph in-memory checkpoint store and is not durable across backend restarts. Saved agent configuration, agent health endpoints, persistent run logs, and historical metrics are not currently exposed by the backend; the UI identifies these as unavailable rather than fabricating status or configuration.

Knowledge documents are scoped to a project and either a selected environment or the whole project. Legacy documents without an assigned scope remain visible for reassignment but are not included in scoped retrieval. Ingestion and indexing are synchronous; external source connectors, background ingestion, vector-store administration, and URL crawling are not implemented.

Cloud Integrations stores environment-scoped account and external identity/secret-manager references only. A saved reference is explicitly marked unverified; the UI does not claim provider authentication, resource discovery, or live connection validation. Logs and traces are also unavailable until a query backend is configured. Observability currently combines process-wide cumulative counters, tenant-scoped in-memory LLM telemetry, and selected-workspace in-memory agent runs; these are not historical environment metrics.

Backend errors are presented as errors rather than being converted to successful-looking demo data.

Demo login is opt-in at deployment and displays a persistent **DEMO · READ ONLY**
indicator. Mutation controls are disabled by the frontend permission engine, and
the signed demo-session claim is enforced by the API for every non-read request.
Session and access-token cookies are HttpOnly; login endpoints do not return bearer
tokens in browser-readable JSON.

## Capability boundaries

- Local MCP/cloud discovery adapters are deterministic development adapters, not live cloud integrations. The Cloud Integrations reference catalog is separate from those adapters and does not authenticate or validate provider credentials.
- LLM evaluation currently uses deterministic token-overlap scoring; it does not invoke a model provider.
- The API does not currently expose environment-secret management or billing/quota management. Settings reports these as unavailable instead of displaying local-only pretend values. Cloud identity references are metadata only; add audited provider authentication/validation flows and connect a secret manager before enabling secret operations.
- Destructive operations against Production environments require an explicit confirmation of the environment slug. The API enforces this independently of the frontend prompt.
- Password-reset endpoints are retained for compatibility but return `501 Not Implemented`; no delivery/reset implementation is configured. Use the identity provider's recovery flow or contact an administrator.
- Security status reports authenticated session and audit data available from the API. It does not assert compliance certification, MFA enforcement, or cryptographic checks that the deployment does not report.

## Validation

Run from this directory:

```powershell
npm run typecheck
npm run build
```

`npm run lint` requires an ESLint flat configuration, which is not currently present in this frontend package. Next.js build performs its configured lint and TypeScript checks.
