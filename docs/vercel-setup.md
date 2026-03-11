# Vercel Frontend Deployment Runbook

Frontend deployment for issue #127. This assumes the Next.js proxy route from #132 is already in place.

Related issues: #127 (Vercel frontend), #132 (Next.js proxy route), #85 (Cloud Run backend), #129 (Gmail OAuth redirects).

---

## Prerequisites

- Cloud Run backend deployed or deployable from this repo
- Cloud Run service URL available or discoverable with `gcloud`
- `AGENT_API_KEY` already created in Secret Manager or otherwise available
- Vercel account with access to the target GitHub repo
- `vercel` CLI installed and authenticated, or dashboard access as a fallback

The production env contract is:

- `API_BASE_URL=<bare Cloud Run service URL>`
- `AGENT_API_KEY=<bearer token>`

Do not use `NEXT_PUBLIC_API_BASE_URL` or any public env var for the token.

---

## 1. Get the Cloud Run backend URL

If the backend is already deployed:

```bash
PROJECT_ID="your-gcp-project-id"
REGION="your-gcp-region"  # e.g. europe-west2 for London

gcloud run services describe personal-agent-backend \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(status.url)"
```

Expected output:

```text
https://personal-agent-backend-<hash>-uc.a.run.app
```

If no service URL exists yet, deploy the backend first using [`cloud-run-setup.md`](cloud-run-setup.md).

---

## 2. Get the bearer token

If the token is stored in Secret Manager:

```bash
PROJECT_ID="your-gcp-project-id"

gcloud secrets versions access latest \
  --secret=personal-agent-agent-api-key \
  --project="${PROJECT_ID}"
```

You need this value for the private Vercel `AGENT_API_KEY` env var.

---

## 3. Install and authenticate the Vercel CLI

If `vercel` is not installed:

```bash
npm install -g vercel
```

Authenticate:

```bash
vercel login
```

If CLI setup is blocked, use the Vercel dashboard as a fallback and keep the same env var names described below.

---

## 4. Link or create the Vercel project

From the frontend directory:

```bash
cd frontend
vercel link
```

Choose the existing project if one already exists; otherwise create a new one. Keep the project rooted at `frontend/`.

If Git integration is offered, enable it so pushes can trigger future preview/production deploys automatically.

---

## 5. Configure Vercel environment variables

Set both env vars for `production` and `preview`:

```bash
cd frontend
vercel env add API_BASE_URL production
vercel env add API_BASE_URL preview
vercel env add AGENT_API_KEY production
vercel env add AGENT_API_KEY preview
```

Use the bare Cloud Run origin for `API_BASE_URL`, for example:

```text
https://personal-agent-backend-<hash>-uc.a.run.app
```

Do not append `/api/v1`. The Next.js proxy route maps browser requests onto the backend paths itself.

---

## 6. Run the first deploy

From `frontend/`:

```bash
vercel --prod
```

Record the production frontend URL, for example:

```text
https://personal-agent.vercel.app
```

If preview deployments are enabled through Git integration, keep the preview URL as a secondary verification target.

---

## 7. Redeploy the backend with the Vercel origin

After the first Vercel deploy, update backend CORS:

```bash
PROJECT_ID="your-gcp-project-id"
REGION="your-gcp-region"  # e.g. europe-west2 for London
VERCEL_URL="https://personal-agent.vercel.app"

VERCEL_URL="${VERCEL_URL}" \
  deploy/deploy-backend.sh --project "${PROJECT_ID}" --region "${REGION}"
```

This refreshes the Cloud Run service with the correct frontend origin in the allowlist.

---

## 8. Verify the deployed path

Verify the backend directly:

```bash
PROJECT_ID="your-gcp-project-id"
REGION="your-gcp-region"  # e.g. europe-west2 for London
AGENT_API_KEY="$(gcloud secrets versions access latest \
  --secret=personal-agent-agent-api-key \
  --project="${PROJECT_ID}")"
SERVICE_URL="$(gcloud run services describe personal-agent-backend \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(status.url)")"

curl -sSf -H "Authorization: Bearer ${AGENT_API_KEY}" \
  "${SERVICE_URL}/api/v1/health"
```

Verify the Vercel proxy path:

```bash
curl -sSf "https://<your-project>.vercel.app/api/agent/health"
```

Then do a browser smoke test:

- Load `/`
- Confirm the app renders without client-side secret exposure
- Trigger one agent request through `/api/agent/...`
- Confirm activity/metrics pages load

---

## 9. Record URLs for follow-up work

Keep both deployed origins available for later tasks:

- Cloud Run service URL for scheduler jobs and backend checks
- Vercel production URL for CORS and Gmail OAuth redirect updates in #129

Gmail callback target remains:

```text
<CLOUD_RUN_URL>/api/v1/gmail/callback
```

The Vercel origin should also be added to the Google Cloud OAuth client configuration when #129 is implemented.
