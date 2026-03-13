#!/bin/bash
PROJECT=personal-agent-490102

echo "Step 4: Create Artifact Registry"
gcloud artifacts repositories create personal-agent \
  --repository-format=docker \
  --location=europe-west2 \
  --description="Personal Agent container images" \
  --project=$PROJECT || true

echo "Step 5: Create Cloud SQL Instance"
gcloud sql instances create personal-agent-db \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=europe-west2 \
  --project=$PROJECT || echo "Instance may already exist."

gcloud sql databases create personal_agent \
  --instance=personal-agent-db \
  --project=$PROJECT || true

DB_PASSWORD=$(openssl rand -hex 32)
echo "DB_PASSWORD=$DB_PASSWORD" > db_creds.txt

gcloud sql users create personal_agent \
  --instance=personal-agent-db \
  --password="$DB_PASSWORD" \
  --project=$PROJECT || gcloud sql users set-password personal_agent \
  --instance=personal-agent-db \
  --password="$DB_PASSWORD" \
  --project=$PROJECT

DATABASE_URL="postgresql+psycopg://personal_agent:${DB_PASSWORD}@/personal_agent?host=/cloudsql/personal-agent-490102:europe-west2:personal-agent-db"
echo "DATABASE_URL=$DATABASE_URL" >> db_creds.txt

echo "Step 6: Service Accounts"
SA=github-actions@personal-agent-490102.iam.gserviceaccount.com
gcloud iam service-accounts create github-actions \
  --display-name="GitHub Actions" \
  --project=$PROJECT || true

for role in roles/run.admin roles/artifactregistry.writer roles/iam.serviceAccountUser roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member="serviceAccount:$SA" \
    --role="$role"
done

PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format="value(projectNumber)")
CLOUDRUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for role in roles/cloudsql.client roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member="serviceAccount:$CLOUDRUN_SA" \
    --role="$role"
done

echo "Step 7: WIF setup"
REPO=gtpooniwala/personal-agent

gcloud iam workload-identity-pools create "github-actions-pool" \
  --location="global" \
  --display-name="GitHub Actions Pool" \
  --project=$PROJECT || true

gcloud iam workload-identity-pools providers create-oidc "github-actions-provider" \
  --location="global" \
  --workload-identity-pool="github-actions-pool" \
  --display-name="GitHub Actions Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.actor=assertion.actor,attribute.ref=assertion.ref" \
  --attribute-condition="assertion.repository=='${REPO}'" \
  --project=$PROJECT || true

gcloud iam service-accounts add-iam-policy-binding $SA \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/github-actions-pool/attribute.repository/${REPO}" \
  --project=$PROJECT

WIF_PROVIDER=$(gcloud iam workload-identity-pools providers describe github-actions-provider \
  --location="global" \
  --workload-identity-pool="github-actions-pool" \
  --project=$PROJECT \
  --format="value(name)")
echo "WIF_PROVIDER=$WIF_PROVIDER" >> db_creds.txt
cat db_creds.txt
