# Cloud Run Backend Setup Runbook

One-time setup and ongoing operations for the `personal-agent-backend` Cloud Run service.

Related issues: #85 (this runbook), #82 (Secret Manager secrets), #80 (Cloud SQL / DATABASE_URL),
#83 (bearer-token auth middleware), #127 (Vercel frontend), #88 (Cloud Scheduler jobs).

---

## Prerequisites

- `gcloud` CLI authenticated with the target GCP project
- Cloud SQL instance provisioned and `DATABASE_URL` secret created (#80)
- Docker installed locally (for `deploy/deploy-backend.sh`)

> **Ordering note:** `docs/secret-manager-setup.md` (#82) requires the Cloud Run
> service account to already exist. Complete §1–3 of this runbook first (create the
> service account + IAM grants), then run the Secret Manager setup, then continue
> with §4 (Artifact Registry) and §5 (deploy).

---

## 1. Set variables

```bash
PROJECT_ID="your-gcp-project-id"
REGION="your-gcp-region"  # e.g. europe-west2 for London
CR_SA="personal-agent-backend@${PROJECT_ID}.iam.gserviceaccount.com"
```

---

## 2. Enable required APIs

Skip any already enabled (Cloud SQL API was enabled in #80).

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  --project="${PROJECT_ID}"
```

---

## 3. Create the Cloud Run service account

```bash
gcloud iam service-accounts create personal-agent-backend \
  --display-name="personal-agent Cloud Run backend" \
  --project="${PROJECT_ID}"
```

Grant Secret Manager read access (must run after secrets are created in #82):

```bash
for SECRET in \
  personal-agent-agent-api-key \
  personal-agent-gemini-api-key \
  personal-agent-database-url; do
  gcloud secrets add-iam-policy-binding "${SECRET}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:${CR_SA}" \
    --role="roles/secretmanager.secretAccessor"
done
```

Grant Cloud SQL client access for private IP connections:

```bash
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${CR_SA}" \
  --role="roles/cloudsql.client"
```

---

## 4. Create the Artifact Registry repository

```bash
gcloud artifacts repositories create personal-agent \
  --repository-format=docker \
  --location="${REGION}" \
  --description="personal-agent container images" \
  --project="${PROJECT_ID}"
```

Authenticate Docker to Artifact Registry:

```bash
gcloud auth configure-docker "${REGION}-docker.pkg.dev"
```

---

## 5. Deploy the backend

Run the deploy script from the repository root:

```bash
deploy/deploy-backend.sh --project "${PROJECT_ID}" --region "${REGION}"
```

The script:
1. Builds and pushes the Docker image to Artifact Registry
2. Renders `deploy/cloud-run-backend.yaml` with the correct project/region/image values
3. Deploys via `gcloud run services replace`
4. Opens unauthenticated HTTP invocations (access control is enforced in-app by the bearer-token middleware)
5. Prints the service URL

---

## 6. Record the service URL

After the first successful deploy, the script prints the service URL:

```
Service URL : https://personal-agent-backend-<hash>-uc.a.run.app
```

**This URL is needed by:**

| Consumer | Where to set it | Issue |
|----------|----------------|-------|
| Vercel frontend | `API_BASE_URL = <SERVICE_URL>` and `AGENT_API_KEY = <token>` (private Vercel env vars) | #127 / #132 |
| Gmail OAuth redirect URIs | Add `<SERVICE_URL>/api/v1/gmail/callback` to Google Cloud Console | #129 |
| Cloud Scheduler jobs | HTTP target base URL for trigger endpoints | #88 |

For Vercel, use the bare Cloud Run origin exactly as printed above. Do not append `/api/v1` and do not use a `NEXT_PUBLIC_*` variable for this value. The Next.js app forwards requests through its same-origin `/api/agent/...` proxy.

See [`vercel-setup.md`](vercel-setup.md) for the full frontend deployment flow.

---

## 7. Deploy the frontend in Vercel

Use the Cloud Run service URL from §6 as the Vercel `API_BASE_URL`, set the private `AGENT_API_KEY`, and complete the first frontend deploy using [`vercel-setup.md`](vercel-setup.md).

Record the Vercel URL after that first deploy. It is needed for backend CORS and later Gmail OAuth redirect updates.

---

## 8. Update CORS after Vercel deploy

Once the Vercel URL is known (e.g. `https://personal-agent.vercel.app`), pass it as an environment variable and redeploy (no script edits required):

```bash
VERCEL_URL="https://personal-agent.vercel.app" \
  deploy/deploy-backend.sh --project "${PROJECT_ID}" --region "${REGION}"
```

---

## 9. Verify the deployment

Check the service is running:

```bash
gcloud run services describe personal-agent-backend \
  --region="${REGION}" \
  --project="${PROJECT_ID}"
```

Smoke-test the health endpoint (requires the bearer token from Secret Manager):

```bash
AGENT_API_KEY="$(gcloud secrets versions access latest \
  --secret=personal-agent-agent-api-key \
  --project="${PROJECT_ID}")"

SERVICE_URL="$(gcloud run services describe personal-agent-backend \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(status.url)")"

curl -sSf -H "Authorization: Bearer ${AGENT_API_KEY}" \
  "${SERVICE_URL}/api/v1/health" \
  && echo "Health check passed" \
  || { echo "Health check FAILED — check service logs"; false; }
```

Expected: `{"status": "healthy", ...}` with HTTP 200.

Then verify the frontend proxy end to end through the deployed Vercel app:

```bash
curl -sSf "https://<your-project>.vercel.app/api/agent/health"
```

If the backend is auth-enabled and Vercel env vars are set correctly, the proxy should return the backend health payload without exposing `AGENT_API_KEY` to the browser.

---

## Operations

### Redeploy (new image)

```bash
deploy/deploy-backend.sh --project "${PROJECT_ID}" --region "${REGION}"
```

### View logs

```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=personal-agent-backend" \
  --project="${PROJECT_ID}" \
  --limit=50 \
  --format="value(timestamp, textPayload)"
```

Or stream live:

```bash
gcloud beta run services logs tail personal-agent-backend \
  --region="${REGION}" \
  --project="${PROJECT_ID}"
```

### Rotate a secret

Add a new version in Secret Manager; Cloud Run picks it up on the next cold start
or container restart. No service update required.

```bash
echo -n "new-value" | gcloud secrets versions add personal-agent-gemini-api-key \
  --project="${PROJECT_ID}" \
  --data-file=-
```

### Scale settings

`min-instances=0` is final for this project (see `DEPLOYMENT.md §7`).
`max-instances=3` is the current cap; adjust in `deploy/cloud-run-backend.yaml`
if traffic increases.

---

## Architecture notes

- **Scale to zero** (`min-instances=0`): cold starts ~2–3 s; acceptable for personal use.
  Cloud Scheduler jobs (#88) send HTTP requests to wake the container for periodic tasks.
- **Bearer-token auth**: `AGENT_API_KEY` is injected from Secret Manager at startup.
  All routes including `/api/v1/health` require the token. See `DEPLOYMENT.md §5`.
- **Cloud SQL Auth Connector**: Cloud Run mounts a unix socket via the
  `run.googleapis.com/cloudsql-instances` annotation. `DATABASE_URL` uses
  `?host=/cloudsql/<CONNECTION_NAME>`. No VPC connector needed (#80).
- **Unauthenticated HTTP**: Cloud Run IAM is open (`allUsers` → `roles/run.invoker`);
  security is enforced entirely by the in-app bearer-token middleware.
- **Health probes**: use a TCP startup probe only. `/api/v1/health` requires a bearer
  token that probe definitions cannot reference dynamically, and Cloud Run does not accept
  TCP liveness probes. The startup probe confirms the port is bound before serving traffic;
  full app readiness (DB pool, etc.) is not verified by the probe.
- **Gmail integration**: the Cloud Run service leaves Gmail enabled so production matches
  the app's default feature flags, but the Gmail tool still self-disables unless
  `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`,
  `CREDENTIALS_MASTER_KEY`, and Gmail dependencies are present. Gmail user tokens are
  stored encrypted in Postgres, so a persistent volume is no longer required. Final
  production Gmail OAuth wiring remains tracked in #129.
