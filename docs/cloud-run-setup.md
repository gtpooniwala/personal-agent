# Cloud Run Backend Setup Runbook

One-time setup and ongoing operations for the `personal-agent-backend` Cloud Run service.

Related issues: #85 (this runbook), #82 (Secret Manager secrets), #80 (Cloud SQL / DATABASE_URL),
#83 (bearer-token auth middleware), #127 (Vercel frontend), #88 (Cloud Scheduler jobs).

---

## Prerequisites

- `gcloud` CLI authenticated with the target GCP project
- Cloud SQL instance provisioned and `DATABASE_URL` secret created (#80)
- Secrets created in Secret Manager (#82): `personal-agent-agent-api-key`,
  `personal-agent-gemini-api-key`, `personal-agent-database-url`
- Docker installed locally (for `deploy/deploy-backend.sh`)

---

## 1. Set variables

```bash
PROJECT_ID="your-gcp-project-id"
REGION="us-central1"
CR_SA="personal-agent-backend@${PROJECT_ID}.iam.gserviceaccount.com"
```

---

## 2. Enable required APIs

Skip any already enabled (Cloud SQL API was enabled in #80).

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  vpcaccess.googleapis.com \
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

## 5. Create the VPC connector

Required for Cloud Run to reach Cloud SQL over private IP (#80).

```bash
gcloud compute networks vpc-access connectors create personal-agent-connector \
  --region="${REGION}" \
  --network=default \
  --range="10.8.0.0/28" \
  --project="${PROJECT_ID}"
```

> The CIDR range `10.8.0.0/28` must not overlap with other subnets in the VPC.
> Adjust if needed.

---

## 6. Deploy the backend

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

## 7. Record the service URL

After the first successful deploy, the script prints the service URL:

```
Service URL : https://personal-agent-backend-<hash>-uc.a.run.app
```

**This URL is needed by:**

| Consumer | Where to set it | Issue |
|----------|----------------|-------|
| Vercel frontend | `NEXT_PUBLIC_API_BASE_URL = <SERVICE_URL>/api/v1` (private Vercel env var) | #127 |
| Gmail OAuth redirect URIs | Add `<SERVICE_URL>/api/v1/gmail/callback` to Google Cloud Console | #129 |
| Cloud Scheduler jobs | HTTP target base URL for trigger endpoints | #88 |

---

## 8. Update CORS after Vercel deploy

Once the Vercel URL is known (e.g. `https://personal-agent.vercel.app`), update
`VERCEL_URL` in `deploy/deploy-backend.sh` and redeploy:

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

curl -sf -H "Authorization: Bearer ${AGENT_API_KEY}" \
  "${SERVICE_URL}/api/v1/health" | python3 -m json.tool
```

Expected: `{"status": "ok", ...}` with HTTP 200.

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
gcloud alpha run services logs tail personal-agent-backend \
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
- **VPC connector**: routes traffic to Cloud SQL private IP; public IP is not exposed.
- **Unauthenticated HTTP**: Cloud Run IAM is open (`allUsers` → `roles/run.invoker`);
  security is enforced entirely by the in-app bearer-token middleware.
- **Health probes**: TCP socket probes (not HTTP) because `/api/v1/health` requires
  a bearer token that probe definitions cannot reference dynamically.
