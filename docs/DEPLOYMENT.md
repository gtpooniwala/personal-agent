# GCP Deployment Architecture

Last updated: March 8, 2026

This document is the architecture decision record (ADR) and deployment plan for moving from local Docker Compose to Google Cloud Platform (GCP) for personal cloud use.

Current status:
- this is still a planning ADR, not a record of completed cloud rollout work,
- issue [#81](https://github.com/gtpooniwala/personal-agent/issues/81) remains open specifically so this document can stay current as decisions are finalized.

---

## Current State

Three-container Docker Compose setup:
- `postgres` — Postgres database
- `personal-agent` — FastAPI backend on port 8000
- `frontend` — Next.js frontend

Limitations:
- Runs only on local machine; no remote access
- Local `./data` volume is local-only and not backed up (data loss risk)
- No auth; exposed to anyone on the network
- No CI/CD deploy path
- Runtime automation primitives exist locally, but external trigger and deployment behavior are not yet productionized

---

## Target Architecture

### Services

| Component | GCP Service | Notes |
|-----------|-------------|-------|
| Backend (FastAPI) | Cloud Run | Stateless container; auto-scales |
| Frontend (Next.js) | Cloud Run or Firebase Hosting | See decision below |
| Database | Cloud SQL (Postgres) | Managed, auto-backups |
| Document storage | Cloud Storage (GCS) | Replaces ephemeral `./data` volume |
| Secrets | Secret Manager | All API keys and OAuth credentials |
| Auth | Identity-Aware Proxy (IAP) | Google account gates access |
| CI/CD | GitHub Actions → Cloud Run | Deploy on merge to main |

---

## Architecture Decisions

### 1. Compute: Cloud Run (preferred, not final)

**Preference:** Cloud Run for backend and frontend.

**Rationale:**
- No Kubernetes complexity for a personal-use project
- Automatic HTTPS on `*.run.app` domains
- Pay per request; scale to zero when idle
- Same container image as local Docker; minimal code changes

**Other options considered:**

| Option | Cost (personal) | Notes |
|--------|----------------|-------|
| **Cloud Run** | ~$0–15/mo | Preferred. Scale to zero, managed HTTPS, no VM to maintain |
| **Compute Engine (VM)** | ~$7–20/mo always-on | Simplest migration path — run Docker Compose directly on the VM. No GCS migration required for local filesystem. Valid faster-path option. |
| **GKE** | ~$75+/mo | Overkill for personal use |
| **App Engine** | ~$5–20/mo | Older, less flexible, harder to migrate existing Docker setup |

**Faster alternative:** If the priority is "get it running in the cloud quickly," a Compute Engine VM is simpler — you run Docker Compose on it and skip the GCS migration. Cloud Run is the better long-term choice but has more setup steps and requires the GCS migration (#79) before it works correctly. Decide based on timeline.

**Decision deferred on min-instances:** The choice of `min-instances=0` vs `min-instances=1` has significant implications for the event trigger architecture and is linked to that decision. See #87 (cold start) and #88 (event trigger framework). Discuss during implementation.

---

### 2. Database: Cloud SQL (Postgres)

**Decision:** Use Cloud SQL (Postgres) in production.

**Rationale:**
- Already wired in `docker-compose.yml`; just point `DATABASE_URL` at Cloud SQL
- Managed backups, patching, and failover
- Private IP via VPC connector for secure backend access

**Action required:** Configure VPC connector so Cloud Run backend reaches Cloud SQL over private IP. Avoid public IP exposure.

---

### 3. Document Storage: Google Cloud Storage

**Decision:** Migrate from local `./data` volume to GCS.

**Rationale:** Cloud Run has an ephemeral filesystem. Anything written to disk is lost on container restart or scale-in. All document uploads must go to GCS.

**This is a code change** tracked separately in a sub-issue. The backend file-handling paths need to be updated to use the GCS SDK.

---

### 4. Secrets: Secret Manager

**Decision:** Store all secrets in Secret Manager; inject into Cloud Run at startup.

Secrets to migrate:
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`
- Database connection string
- Any future API keys

**Action required:** Grant Cloud Run service account `roles/secretmanager.secretAccessor`.

---

### 5. Auth: Identity-Aware Proxy (IAP)

**Decision:** Use IAP for personal authentication.

**Rationale:**
- Simplest personal-use auth; Google account gates all access
- No login flows to build or maintain
- IAP sits in front of the Cloud Run service; the app itself requires no auth code changes

**Action required:** Enable IAP on the backend Cloud Run service. Allowlist your Google account.

**Deferred: Frontend-to-backend API calls through IAP**
IAP works well for browser requests (it redirects to a Google login page). However, when the Next.js frontend makes `fetch()` API calls to the backend, those are not browser navigations — they need to include an IAP identity token in the `Authorization` header. Getting and refreshing that token in the frontend adds complexity. The resolution depends on how the frontend is hosted:
- If the frontend is on Cloud Run behind IAP too, service-to-service auth (using a GCP service account) is one path
- If the frontend is on Vercel or Firebase Hosting (outside GCP), it needs to obtain a user identity token via Google Sign-In and pass it to the backend

This needs to be worked out during implementation of #83 (IAP) alongside the frontend hosting decision (#85).

---

### 6. Frontend Hosting: Decision Deferred

**Decision deferred** — to be finalized during implementation of #85 (Cloud Run service definitions).

Key prerequisite question: does the Next.js app use server-side rendering (SSR) or Next.js API routes? Check `next.config.js` before deciding. If yes, options B and D below require code changes.

| Option | Pros | Cons |
|--------|------|------|
| **A: Cloud Run** | Consistent deploy model; no code changes; works with SSR | Slightly higher latency than CDN; not optimized for static assets |
| **B: Firebase Hosting** | Better CDN; generous free tier | Requires `output: 'export'` in `next.config.js`; dynamic routes may need refactoring |
| **C: Cloud Run + Cloud CDN** | CDN performance with full Next.js support | More infrastructure; adds cost and complexity |
| **D: Vercel** | Purpose-built for Next.js; zero config; excellent CDN; preview deploys | Outside GCP ecosystem; IAP integration more complex (see §5); separate billing |

**Notes:**
- Vercel is the most ergonomic option for a Next.js project and worth considering if you want the smoothest frontend deployment experience. The tradeoff is that it lives outside GCP, which complicates IAP integration.
- For initial deploy, Cloud Run (Option A) is the lowest friction path and keeps everything in one ecosystem.
- Revisit if CDN performance or Vercel's developer experience matters more than ecosystem consistency.

---

### 7. Cold Starts and min-instances

**Default preference:** `min-instances=0` (scale to zero).

**Rationale:** Personal use; occasional cold starts of ~2-3s are acceptable. Free when idle.

**Optional:** Set `min-instances=1` on the backend if always-warm is preferred. Adds approximately $5-15/month.

**Decision linked to event trigger architecture (#88):** This is not just a cost/latency tradeoff. The min-instances setting determines which trigger architectures are viable:

- **`min-instances=0` (scale to zero):** Internal polling loops (email poller, scheduler heartbeat) don't run when the container is idle — there's no process alive to do the polling. Push-based and webhook-based triggers (Telegram webhook, Cloud Scheduler sending an HTTP request to wake the container) still work fine because an incoming HTTP request wakes the container.
- **`min-instances=1` (always warm):** Internal polling loops work because the container is always running. Simpler trigger implementations, but adds fixed monthly cost.

The event trigger framework design depends on this choice. If scale-to-zero is preferred, polling-based triggers (email, scheduled tasks) need to be driven externally (e.g. Cloud Scheduler sends an HTTP request to a trigger endpoint, which then does the poll and dispatch). This is a valid architecture but changes the implementation. Discuss during #87 (cold start) and #88 (trigger framework).

---

### 8. Networking and Domains

- Cloud Run provides automatic HTTPS on `*.run.app` — no TLS setup needed
- Custom domain: use Cloud Run domain mapping (e.g. `agent.yourdomain.com`)
- Backend and frontend communicate via internal Cloud Run service URLs (no public internet hop)
- Cloud SQL: private IP via VPC connector; do not expose public IP

---

## Deployment Plan (Ordered)

1. **Keep the ADR current** (#81) — resolve remaining frontend hosting and auth boundary decisions
2. **Cloud SQL** (#80) — provision instance, migrate schema, update `DATABASE_URL`
3. **Secret Manager** (#82) — migrate all secrets, update Cloud Run service account
4. **GCS** (#79) — create bucket, update backend file-handling code
5. **Backend and frontend Cloud Run services** (#85)
6. **IAP** (#83) — enable authentication boundary for personal cloud access
7. **CI/CD** (#86) — build and deploy on merge to `main`
8. **Cold-start tuning** (#87) — optimize once the baseline deployment exists
9. **Custom domain** (optional)

---

## Things Not to Forget

- **GCS migration is required** — local `./data` volume is ephemeral on Cloud Run; documents will not persist without this change
- **IAP** — without it, the backend is exposed on the public internet
- **Gmail OAuth redirect URIs** — must be updated to include the Cloud Run or custom domain URL in the Google Cloud Console
- **VPC connector** — needed for Cloud SQL private IP access from Cloud Run
- **Custom domain DNS** — if using a custom domain, update DNS records after Cloud Run domain mapping
- **Cost estimate** — approximately $10-30/month depending on Cloud SQL tier and min-instances setting

---

## Sub-issues

| Issue | Title |
|-------|-------|
| #79 | feat: migrate document storage from local filesystem to GCS |
| #80 | feat: Cloud SQL setup and production database configuration |
| #81 | docs: GCP deployment architecture decision record |
| #82 | feat: Secret Manager integration for production API keys |
| #83 | feat: IAP setup for personal cloud authentication |
| #85 | feat: Cloud Run service definitions for backend and frontend |
| #86 | feat: GitHub Actions CI/CD pipeline for Cloud Run deployment |
| #87 | chore: cold start optimization and min-instances strategy for Cloud Run |
