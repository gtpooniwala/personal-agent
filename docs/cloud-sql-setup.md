# Cloud SQL Setup Runbook

Provisions a Cloud SQL Postgres 16 instance for the personal-agent backend and wires it up for Cloud Run via the Cloud SQL Auth Connector (Unix socket). No VPC connector required.

Related issues: #80 (this runbook), #85 (Cloud Run wiring).

---

## Prerequisites

- `gcloud` CLI authenticated with the target project
- Cloud Run service account already created (created in the Cloud Run deployment issue)

---

## 1. Set variables

```bash
PROJECT_ID="your-gcp-project-id"
REGION="us-central1"
INSTANCE_NAME="personal-agent-db"
DB_NAME="personal_agent"
DB_USER="personal_agent"
DB_PASSWORD="$(openssl rand -base64 32)"   # save this securely before continuing
SECRET_NAME="personal-agent-database-url"
CR_SA="personal-agent-backend@${PROJECT_ID}.iam.gserviceaccount.com"
```

> **Save `DB_PASSWORD`** somewhere secure before proceeding — you cannot retrieve it from Cloud SQL later.

---

## 2. Enable APIs

```bash
gcloud services enable sqladmin.googleapis.com secretmanager.googleapis.com \
  --project="${PROJECT_ID}"
```

---

## 3. Create Cloud SQL instance (~10 min)

```bash
gcloud sql instances create "${INSTANCE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --database-version=POSTGRES_16 \
  --tier=db-g1-small \
  --storage-type=SSD \
  --storage-size=10GB \
  --storage-auto-increase \
  --storage-auto-increase-limit=100 \
  --backup \
  --backup-start-time=03:00 \
  --retained-backups-count=7 \
  --no-assign-ip \
  --availability-type=ZONAL
```

`db-g1-small` supports ~25 connections. SQLAlchemy's default pool (5 + overflow 10) is fine at personal scale.

---

## 4. Create database and user

```bash
gcloud sql databases create "${DB_NAME}" \
  --instance="${INSTANCE_NAME}" \
  --project="${PROJECT_ID}"

gcloud sql users create "${DB_USER}" \
  --instance="${INSTANCE_NAME}" \
  --password="${DB_PASSWORD}" \
  --project="${PROJECT_ID}"
```

---

## 5. Store DATABASE_URL in Secret Manager

The URL uses the Cloud SQL Auth Connector socket path — no host/port needed.

```bash
CONNECTION_NAME=$(gcloud sql instances describe "${INSTANCE_NAME}" \
  --project="${PROJECT_ID}" \
  --format="value(connectionName)")

DATABASE_URL="postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${CONNECTION_NAME}"

echo -n "${DATABASE_URL}" | gcloud secrets create "${SECRET_NAME}" \
  --project="${PROJECT_ID}" \
  --replication-policy=automatic \
  --data-file=-
```

> The secret name `personal-agent-database-url` must match exactly what issue #85 uses for `--set-secrets`.

---

## 6. IAM grants

Grant the Cloud Run service account permission to connect to Cloud SQL and read the secret.

```bash
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${CR_SA}" \
  --role="roles/cloudsql.client"

gcloud secrets add-iam-policy-binding "${SECRET_NAME}" \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:${CR_SA}" \
  --role="roles/secretmanager.secretAccessor"
```

---

## 7. Schema initialisation

The ORM calls `create_all()` on startup (`backend/database/operations.py`). The first Cloud Run container start after deployment will create all tables automatically — no manual migration needed for a fresh instance.

For local dev databases already in use, add the `file_content` column manually:

```sql
ALTER TABLE documents ADD COLUMN file_content BYTEA;
```

---

## Verification

### Check tables via Cloud SQL Proxy

```bash
# Download the proxy binary if needed:
# https://cloud.google.com/sql/docs/postgres/connect-auth-proxy

./cloud-sql-proxy "${CONNECTION_NAME}" --port=5434 &

PGPASSWORD="${DB_PASSWORD}" psql \
  -h 127.0.0.1 -p 5434 \
  -U "${DB_USER}" -d "${DB_NAME}" \
  -c "\dt"
```

Expect all ORM tables listed. Confirm `file_content` column is present:

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'documents'
  AND column_name = 'file_content';
```

### After a PDF upload

```sql
SELECT id, length(file_content) FROM documents;
```

Expect non-null, non-zero values. The `data/uploads/` directory on the Cloud Run filesystem will remain empty.

---

## Notes

- `--no-assign-ip` means the instance has no public IP — access is only via Cloud SQL Auth Connector (socket) or Cloud SQL Proxy.
- PDF binary size is capped at 50 MB in `backend/routes.py`; PostgreSQL BYTEA has no practical limit below that.
- `db-g1-small` is sufficient for personal scale. Upgrade to `db-custom-1-3840` if query latency degrades under load.
