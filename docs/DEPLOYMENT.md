# GCP Deployment Architecture

Last updated: March 7, 2026

This document is the architecture decision record (ADR) and deployment plan for moving from local Docker Compose to Google Cloud Platform (GCP) for personal cloud use.

---

## Current State

Three-container Docker Compose setup:
- `postgres` — Postgres database
- `personal-agent` — FastAPI backend on port 8000
- `frontend` — Next.js frontend

Limitations:
- Runs only on local machine; no remote access
- Local `./data` volume is ephemeral and not backed up
- No auth; exposed to anyone on the network
- No CI/CD deploy path

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

### 1. Compute: Cloud Run (not GKE)

**Decision:** Deploy backend and frontend as separate Cloud Run services.

**Rationale:**
- No Kubernetes complexity for a personal-use project
- Automatic HTTPS on `*.run.app` domains
- Pay per request; scale to zero when idle
- Same container image as local Docker; minimal code changes

**Rejected:** GKE — overkill for personal use, higher baseline cost.

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

---

### 6. Frontend Hosting: Decision Deferred

Three options — choose at deploy time:

| Option | Pros | Cons |
|--------|------|------|
| **A: Cloud Run** | Consistent deploy model; no code changes | Slightly higher latency than CDN; not optimized for static assets |
| **B: Firebase Hosting** | Better CDN; free tier | Requires Next.js static export (`output: 'export'`); may need code changes for dynamic routes |
| **C: Cloud Run + Cloud CDN** | Best of both; CDN in front of Cloud Run | More infrastructure to manage |

**Recommendation for initial deploy:** Option A (Cloud Run). Switch to Firebase Hosting or Cloud CDN if CDN performance matters later.

---

### 7. Cold Starts

**Decision:** Default to `min-instances=0` (scale to zero).

**Rationale:** Personal use; occasional cold starts of ~2-3s are acceptable.

**Optional:** Set `min-instances=1` on the backend if always-warm is preferred. Adds approximately $5-15/month.

---

### 8. Networking and Domains

- Cloud Run provides automatic HTTPS on `*.run.app` — no TLS setup needed
- Custom domain: use Cloud Run domain mapping (e.g. `agent.yourdomain.com`)
- Backend and frontend communicate via internal Cloud Run service URLs (no public internet hop)
- Cloud SQL: private IP via VPC connector; do not expose public IP

---

## Deployment Plan (Ordered)

1. **Cloud SQL** — provision instance, migrate schema, update `DATABASE_URL`
2. **Secret Manager** — migrate all secrets, update Cloud Run service account
3. **GCS** — create bucket, update backend file-handling code (tracked separately)
4. **Backend Cloud Run** — deploy FastAPI service, wire Cloud SQL + secrets + IAP
5. **Frontend Cloud Run** — deploy Next.js service, point at backend URL
6. **IAP** — enable on backend service, allowlist Google account
7. **CI/CD** — add GitHub Actions workflow to build and deploy on merge to main
8. **Custom domain** (optional) — configure Cloud Run domain mapping

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
| #79 | docs: GCP deployment architecture decision record |
| #80 | feat: migrate document storage from local filesystem to GCS |
| #81 | feat: Cloud SQL setup and production database configuration |
| #82 | feat: Cloud Run service definitions for backend and frontend |
| #83 | feat: Secret Manager integration for production API keys |
| #85 | feat: IAP setup for personal cloud authentication |
| #86 | feat: GitHub Actions CI/CD pipeline for Cloud Run deployment |
| #87 | chore: cold start optimization and min-instances strategy for Cloud Run |
