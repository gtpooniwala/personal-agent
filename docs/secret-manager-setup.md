# Secret Manager Setup Runbook

Provisions all application secrets in GCP Secret Manager and grants the Cloud Run service account read access.

Related issues: #82 (this runbook), #80 (DATABASE_URL secret), #85 (Cloud Run wiring via `--set-secrets`).

---

## Prerequisites

- `gcloud` CLI authenticated with the target project
- Cloud Run service account already created (done in #85)
- Secret Manager API enabled (enabled together with Cloud SQL API in #80 — skip if already done)

---

## 1. Set variables

```bash
PROJECT_ID="your-gcp-project-id"
CR_SA="personal-agent-backend@${PROJECT_ID}.iam.gserviceaccount.com"
```

---

## 2. Enable Secret Manager API

Skip if already enabled (done in #80).

```bash
gcloud services enable secretmanager.googleapis.com \
  --project="${PROJECT_ID}"
```

---

## 3. Canonical secret names

The table below is the single source of truth for secret names. Issue #85 references these names in `--set-secrets`.

| Secret Manager name | Cloud Run env var | Required | Notes |
|---|---|---|---|
| `personal-agent-agent-api-key` | `AGENT_API_KEY` | Yes | Bearer token for FastAPI auth middleware |
| `personal-agent-gemini-api-key` | `GEMINI_API_KEY` | Yes | Primary LLM provider |
| `personal-agent-openai-api-key` | `OPENAI_API_KEY` | No | Fallback LLM provider |
| `personal-agent-database-url` | `DATABASE_URL` | Yes | Created in #80; skip creation here |
| `personal-agent-google-oauth-client-id` | `GOOGLE_OAUTH_CLIENT_ID` | Yes for Gmail | Google OAuth web client ID |
| `personal-agent-google-oauth-client-secret` | `GOOGLE_OAUTH_CLIENT_SECRET` | Yes for Gmail | Google OAuth web client secret |
| `personal-agent-google-oauth-redirect-uri` | `GOOGLE_OAUTH_REDIRECT_URI` | Yes for Gmail | Production should use the frontend proxy callback, e.g. `https://<vercel-app>/api/agent/gmail/callback` |
| `personal-agent-credentials-master-key` | `CREDENTIALS_MASTER_KEY` | Yes for Gmail | Fernet key used to encrypt per-user integration credentials in Postgres |
| `personal-agent-langfuse-public-key` | `LANGFUSE_PUBLIC_KEY` | No | Observability (Langfuse) |
| `personal-agent-langfuse-secret-key` | `LANGFUSE_SECRET_KEY` | No | Observability (Langfuse) |
| `personal-agent-todoist-api-token` | `TODOIST_API_TOKEN` | No | Todoist task integration (not implemented yet; backend does not read this secret) |

---

## 4. Create required secrets

### AGENT_API_KEY (bearer token)

Generate a long random token first, then store it.

```bash
AGENT_API_KEY_VALUE="$(openssl rand -base64 48)"
echo "Save this token — it is also needed as a Vercel env var for #127:"
echo "${AGENT_API_KEY_VALUE}"

echo -n "${AGENT_API_KEY_VALUE}" | gcloud secrets create personal-agent-agent-api-key \
  --project="${PROJECT_ID}" \
  --replication-policy=automatic \
  --data-file=-
```

> **Save the token** — you cannot retrieve the secret value from Secret Manager after creation without an extra `gcloud secrets versions access` call. You will also need it as a **private** Vercel env var (`AGENT_API_KEY`) for issue #127.

### GEMINI_API_KEY

```bash
echo -n "your-gemini-api-key" | gcloud secrets create personal-agent-gemini-api-key \
  --project="${PROJECT_ID}" \
  --replication-policy=automatic \
  --data-file=-
```

### Gmail / Google OAuth secrets

```bash
echo -n "your-google-oauth-client-id" | gcloud secrets create personal-agent-google-oauth-client-id \
  --project="${PROJECT_ID}" \
  --replication-policy=automatic \
  --data-file=-

echo -n "your-google-oauth-client-secret" | gcloud secrets create personal-agent-google-oauth-client-secret \
  --project="${PROJECT_ID}" \
  --replication-policy=automatic \
  --data-file=-

echo -n "https://<vercel-app>/api/agent/gmail/callback" | gcloud secrets create personal-agent-google-oauth-redirect-uri \
  --project="${PROJECT_ID}" \
  --replication-policy=automatic \
  --data-file=-

python3 -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
# Save the printed value, then:
echo -n "your-credentials-master-key" | gcloud secrets create personal-agent-credentials-master-key \
  --project="${PROJECT_ID}" \
  --replication-policy=automatic \
  --data-file=-
```

---

## 5. Create optional secrets

Only create the secrets below if the corresponding integration is used. Secret Manager charges are negligible for a small number of secrets (6 active versions are free; $0.06/version/month after that).

### OPENAI_API_KEY

```bash
echo -n "your-openai-api-key" | gcloud secrets create personal-agent-openai-api-key \
  --project="${PROJECT_ID}" \
  --replication-policy=automatic \
  --data-file=-
```

### LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY

```bash
echo -n "your-langfuse-public-key" | gcloud secrets create personal-agent-langfuse-public-key \
  --project="${PROJECT_ID}" \
  --replication-policy=automatic \
  --data-file=-

echo -n "your-langfuse-secret-key" | gcloud secrets create personal-agent-langfuse-secret-key \
  --project="${PROJECT_ID}" \
  --replication-policy=automatic \
  --data-file=-
```

### TODOIST_API_TOKEN

```bash
echo -n "your-todoist-api-token" | gcloud secrets create personal-agent-todoist-api-token \
  --project="${PROJECT_ID}" \
  --replication-policy=automatic \
  --data-file=-
```

---

## 6. Grant Cloud Run service account access

Run this for the required secrets that every Cloud Run backend revision mounts.

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

For optional secrets, add them individually as they are created:

```bash
# Example: add access after creating an optional secret
gcloud secrets add-iam-policy-binding personal-agent-openai-api-key \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:${CR_SA}" \
  --role="roles/secretmanager.secretAccessor"
```

If you are enabling Gmail, grant access to the Gmail-specific secrets too:

```bash
for SECRET in \
  personal-agent-google-oauth-client-id \
  personal-agent-google-oauth-client-secret \
  personal-agent-google-oauth-redirect-uri \
  personal-agent-credentials-master-key; do
  gcloud secrets add-iam-policy-binding "${SECRET}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:${CR_SA}" \
    --role="roles/secretmanager.secretAccessor"
done
```

---

## 7. Rotate a secret value

To update a secret value (e.g. after a key rotation), add a new version:

```bash
echo -n "new-key-value" | gcloud secrets versions add personal-agent-gemini-api-key \
  --project="${PROJECT_ID}" \
  --data-file=-
```

Cloud Run always resolves `:latest`, so the new version is picked up on the next container start (deploy or cold start). No Cloud Run service update is required.

---

## Local development

Local dev continues to use `.env` files — no changes to the local workflow. The backend reads all settings via `pydantic-settings` (`backend/config/__init__.py`), which loads `.env` when present and falls back to environment variables otherwise. Cloud Run injects secrets as plain environment variables at startup, so the backend code is unchanged.

---

## Verification

List secrets created in the project:

```bash
gcloud secrets list --project="${PROJECT_ID}"
```

Verify IAM bindings for a secret:

```bash
gcloud secrets get-iam-policy personal-agent-agent-api-key \
  --project="${PROJECT_ID}"
```

Retrieve a secret version to confirm it was stored correctly (use sparingly):

```bash
gcloud secrets versions access latest \
  --secret="personal-agent-agent-api-key" \
  --project="${PROJECT_ID}"
```
