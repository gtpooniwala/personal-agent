# GCP Deployment Architecture

Last updated: March 12, 2026

This document is the architecture decision record (ADR) and deployment plan for moving from local Docker Compose to Google Cloud Platform (GCP) for personal cloud use.

Current status:
- decisions are finalized; this ADR is a record of settled choices (closed via #81).
- core backend deployment baseline is already landed in-repo: Cloud SQL, Secret Manager, bearer auth, Cloud Run backend service definition, and the Next.js agent proxy (`#80`, `#82`, `#83`, `#85`, `#132`).
- a backend GitHub Actions deploy workflow now exists; remaining deployment work is frontend/env/auth hardening (`#127`, `#186`, `#191`, `#86`).

---

## Decisions Finalized

| Topic | Decision |
|-------|----------|
| Compute (backend) | Cloud Run |
| Frontend hosting | Vercel (free hobby tier) |
| Auth | Bearer token (long random key in Secret Manager) |
| Cloud Run min-instances | Backend service: `min-instances=0` (scale-to-zero) |
| Document storage | Deferred — ephemeral OK for initial deploy; GCS is the target (#79) |
| Custom domain | Not initially; `*.run.app` + Vercel-assigned domain |
| Cost estimate | ~$7–25/month (Cloud SQL $7–20, Cloud Run ~$0–5, Vercel free) |

---

## Current State

Three-container Docker Compose setup:
- `postgres` — Postgres database
- `personal-agent` — FastAPI backend on port 8000
- `frontend` — Next.js frontend

Limitations:
- Default developer path still runs locally; remote access depends on finishing the deployment steps below
- Local `./data` volume is local-only and not backed up (data loss risk)
- Local auth is optional today; production/shared exposure still requires `AGENT_API_KEY`
- A backend Cloud Run deploy workflow now exists, but frontend rollout and GitHub-to-GCP auth hardening are still follow-up work
- Runtime automation primitives exist locally, but external trigger and deployment behavior are not yet productionized

---

## Target Architecture

### Services

| Component | Service | Notes |
|-----------|---------|-------|
| Backend (FastAPI) | Cloud Run | Stateless container; scale to zero; `min-instances=0` |
| Frontend (Next.js) | Vercel | Free hobby tier; zero code changes; best Next.js DX |
| Database | Cloud SQL (Postgres) | Managed, auto-backups |
| Document storage | Ephemeral (initial); GCS (target) | Deferred; see §3 and #79 |
| Secrets | Secret Manager | All API keys and OAuth credentials |
| Auth | Bearer token | Long random key; FastAPI middleware; stored in Secret Manager |
| CI/CD | GitHub Actions → Cloud Run | Deploy on merge to main |

---

## Architecture Decisions

### 1. Compute: Cloud Run

**Decision:** Cloud Run for the backend.

**Rationale:**
- No Kubernetes complexity for a personal-use project
- Automatic HTTPS on `*.run.app` domains
- Pay per request; scale to zero when idle
- Same container image as local Docker; minimal code changes

**min-instances: 0 (final)**

Scale to zero. Personal use; occasional cold starts of ~2–3s are acceptable. Free when idle. Cloud Scheduler drives periodic polling triggers via HTTP requests to wake the container — no always-warm container required. See §7.

---

### 2. Database: Cloud SQL (Postgres)

**Decision:** Use Cloud SQL (Postgres) in production.

**Rationale:**
- Already wired in `docker-compose.yml`; just point `DATABASE_URL` at Cloud SQL
- Managed backups, patching, and failover
- Cloud Run can connect through the Cloud SQL Auth Connector (Unix socket), so no VPC connector is required for the current deployment path

**Action required:** Create the Cloud SQL instance and render `DATABASE_URL` with the Cloud SQL Unix socket host (`?host=/cloudsql/<CONNECTION_NAME>`). No VPC connector is required for the current runbook.

---

### 3. Document Storage: Deferred

**Decision:** Deferred from initial deploy. Ephemeral filesystem is acceptable for the initial Cloud Run baseline.

**Target implementation:** GCS (Google Cloud Storage), tracked in #79. Standard Cloud Run pattern; cheaper storage at ~$0.02/GB vs Cloud SQL's ~$0.17/GB for BLOBs; keeps the database lean.

**Note:** Current file handling accepts PDFs only. Multi-format support (Word, txt, images) is a separate concern independent of storage location.

When tackled (#79): add GCS SDK dependency, update file upload/retrieval paths, add `GCS_BUCKET_NAME` env var wired through Secret Manager.

---

### 4. Secrets: Secret Manager

**Decision:** Store all secrets in Secret Manager; inject into Cloud Run at startup.

Secrets to migrate:
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- Database connection string
- `AGENT_API_KEY` (bearer token for auth)
- Any future API keys

**Action required:** Grant Cloud Run service account `roles/secretmanager.secretAccessor`.

---

### 5. Auth: Bearer Token

**Decision:** Bearer token authentication for personal cloud access.

**Implementation:**
- Generate a long random token: `openssl rand -base64 48`
- Store in Secret Manager as `AGENT_API_KEY`
- Set `ENVIRONMENT=production` (or any non-`local` value) in Cloud Run so startup fails fast if the token is missing
- Cloud Run service is deployed with **unauthenticated HTTP invocation enabled** (`--allow-unauthenticated`); access control is enforced entirely by the bearer-token middleware inside the service (no IAP or IAM-based invoker in the request path)
- FastAPI middleware checks `Authorization: Bearer <token>` on every non-`OPTIONS` route when `AGENT_API_KEY` is configured
- There are no anonymous route exemptions in auth-enabled environments: `/api/v1/health`, runtime routes, scheduler routes, `/docs`, `/redoc`, and `/openapi.json` all require the bearer token
- Cloud Run injects `AGENT_API_KEY` from Secret Manager at startup
- Vercel reads `AGENT_API_KEY` as a private env var and injects it server-side via the Next.js API proxy route (#132)
- Cloud Scheduler jobs that call the backend use HTTP targets pointing at the Cloud Run URL and include `Authorization: Bearer <AGENT_API_KEY>` in the request headers

**Why not IAP:** IAP + Vercel requires service-to-service token complexity (identity tokens, refresh logic in the frontend). For personal single-user use, a long random bearer token is simpler and equally secure. No Google account dependency in the auth path.

Tracked in #83.

**Note on browser-side requests:** Browser-side (`"use client"`) components cannot access non-`NEXT_PUBLIC_` env vars, so a Next.js API proxy route is required to inject the bearer token server-side before forwarding requests to Cloud Run. Storing the token as `NEXT_PUBLIC_AGENT_API_KEY` would expose it to all visitors. See #132.

**Operational note on docs:** In auth-enabled environments, `/docs` and `/openapi.json` are also protected. Use authenticated HTTP requests or temporarily run locally without `AGENT_API_KEY` if you need anonymous Swagger access during development.

---

### 6. Frontend Hosting: Vercel

**Decision:** Vercel (free hobby tier).

**Rationale:**
- Purpose-built for Next.js; zero code changes required
- Free for 3–10 DAU indefinitely on the hobby tier
- Best Next.js developer experience; preview deploys included
- `API_BASE_URL` stored as a **private** Vercel env var containing the bare Cloud Run `*.run.app` origin (for example `https://personal-agent-backend-<hash>-uc.a.run.app`); used server-side by the Next.js API proxy route only — not exposed in the browser bundle
- `AGENT_API_KEY` stored as a **private** Vercel env var; injected server-side via the Next.js API proxy route (#132) so the token is never exposed in the browser

Tracked in #127. API proxy route tracked in #132. See [`vercel-setup.md`](vercel-setup.md) for the operator runbook.

---

### 7. Cold Starts and min-instances

**Decision: `min-instances=0` (scale to zero). Final.**

**Rationale:** Personal use; occasional cold starts of ~2–3s are acceptable. Free when idle.

**Trigger architecture with scale-to-zero:**

- Push-based triggers (Cloud Scheduler HTTP requests, Telegram webhooks, incoming webhooks) wake the container via HTTP — fully compatible with `min-instances=0`.
- Polling-based triggers (email poller, scheduler heartbeat) are driven externally: Cloud Scheduler sends HTTP requests to `/triggers/email-poll` and `/triggers/schedule` on a cron cadence, waking the container to do the poll and dispatch.

Cloud Scheduler job provisioning is in scope for #88.

---

### 8. Networking and Domains

- Cloud Run provides automatic HTTPS on `*.run.app` — no TLS setup needed
- Frontend is Vercel-assigned domain (e.g. `personal-agent.vercel.app`)
- Custom domain: can attach an owned domain to Cloud Run or Vercel later; not required initially
- Backend and frontend communicate through the Next.js same-origin `/api/agent/...` proxy; Vercel stores the Cloud Run `*.run.app` URL as private `API_BASE_URL`
- Cloud SQL: accessed from Cloud Run through the Cloud SQL Auth Connector (Unix socket); no VPC connector is required in the current setup
- After the first Vercel deploy, redeploy Cloud Run with `VERCEL_URL=https://<project>.vercel.app` so the backend CORS allowlist matches the frontend origin

---

## Deployment Plan (Ordered)

1. ~~**Cloud SQL** (#80) — provision instance, migrate schema, update `DATABASE_URL`.~~ **Done**
2. ~~**Secret Manager** (#82) — migrate all secrets; add `AGENT_API_KEY`; update Cloud Run service account.~~ **Done**
3. ~~**Bearer token auth middleware** (#83) — FastAPI middleware; generate and store token in Secret Manager.~~ **Done**
4. ~~**Backend Cloud Run service** (#85) — Cloud Run YAML/config; env vars from Secret Manager; Cloud SQL Auth Connector socket mount; `min-instances=0`; deploy backend with auth middleware already in the image; record `*.run.app` URL.~~ **Done**
5. ~~**Next.js API proxy route** (#132) — inject bearer auth server-side for `/api/agent/...` requests.~~ **Done**
6. **Vercel frontend deploy and preview env wiring** (#127, #186) — connect repo, set private env vars, and finish preview/prod validation through `/api/agent/...`
7. **Gmail OAuth redirect URIs** (#129) — add Cloud Run and Vercel URLs to Google Cloud Console OAuth credentials; test Gmail OAuth flow
8. **Backend CI/CD hardening** (#86, #191) — finish the deployment pipeline from the current backend-only workflow and migrate GitHub Actions GCP auth to Workload Identity Federation
9. **Cloud Scheduler provisioning** (#88 follow-up) — wire the remaining polling endpoints/jobs into the deployed environment
10. **GCS document storage** (#79) — when durable document persistence is needed
11. **Cold-start tuning** (#87) — optional; revisit once cloud baseline is running

---

## Things Not to Forget

- **Bearer token** — `AGENT_API_KEY` must be set in both Secret Manager (for Cloud Run) and Vercel env vars before any API calls work end-to-end; without it the backend will reject all requests, and non-local startup should fail immediately
- **GCS migration is not a blocker** — ephemeral storage is acceptable for the initial deploy; documents will not persist across container restarts until #79 is done
- **Gmail OAuth redirect URIs** — must be updated in Google Cloud Console to include Cloud Run and Vercel URLs before Gmail polling works in production (#129)
- **Cloud SQL connectivity** — the current production path uses the Cloud SQL Auth Connector socket mount from Cloud Run; no VPC connector is required by the runbooks
- **Cloud Scheduler jobs** — required for email polling and scheduled task triggers when running at `min-instances=0` (scale to zero); provisioned in #88
- **Custom domain DNS** — if attaching an owned domain later, update DNS records after Cloud Run domain mapping or Vercel domain config
- **Cost estimate** — approximately $7–25/month: Cloud SQL $7–20, Cloud Run ~$0–5, Vercel free

---

## Sub-issues

| Issue | Title |
|-------|-------|
| #79 | feat: migrate document storage from local filesystem to GCS |
| #80 | feat: Cloud SQL setup and production database configuration |
| #81 | docs: GCP deployment architecture decision record |
| #82 | feat: Secret Manager integration for production API keys |
| #83 | feat: bearer token auth middleware for FastAPI backend |
| #85 | feat: Cloud Run service definition for backend |
| #86 | feat: GitHub Actions CI/CD pipeline for Cloud Run deployment |
| #87 | chore: cold start optimization and min-instances strategy for Cloud Run |
| #127 | feat: deploy Next.js frontend to Vercel |
| #186 | chore: configure Vercel preview env vars after Git integration |
| #191 | feat(ops): Migrate GitHub Actions GCP auth to Workload Identity Federation |
| #129 | chore: update Gmail OAuth redirect URIs for production domains |
| #132 | feat: Next.js API proxy route for server-side bearer token injection |
