#!/usr/bin/env bash
# Deploy the personal-agent FastAPI backend to Cloud Run.
#
# Prerequisites (one-time setup):
#   See docs/cloud-run-setup.md for the full runbook.
#
# Usage:
#   deploy/deploy-backend.sh [--project PROJECT_ID] [--region REGION] [--tag TAG]
#
# Options:
#   --project  GCP project ID (default: $GOOGLE_CLOUD_PROJECT or gcloud config)
#   --region   Cloud Run region  (default: us-central1)
#   --tag      Docker image tag  (default: git SHA)
#
# After the first Vercel deploy (#127), pass VERCEL_URL as an env var:
#   VERCEL_URL="https://your-app.vercel.app" deploy/deploy-backend.sh --project ...

set -euo pipefail

# ── Configurable defaults ────────────────────────────────────────────────────

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${CLOUD_RUN_REGION:-us-central1}"

# Service / infra names — must match the values used during one-time setup.
SERVICE_NAME="personal-agent-backend"
AR_REPO="personal-agent"                    # Artifact Registry repository name
INSTANCE_NAME="personal-agent-db"           # Cloud SQL instance name (#80)

# Vercel frontend origin for CORS. Update after the first Vercel deploy (#127).
# Example: "https://personal-agent.vercel.app"
VERCEL_URL="${VERCEL_URL:-}"

# ── Parse args ───────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT_ID="$2"; shift 2 ;;
    --region)  REGION="$2";     shift 2 ;;
    --tag)     TAG="$2";        shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# Default TAG to git SHA after arg parsing so --tag can override it cleanly.
TAG="${TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"

# ── Derived values ───────────────────────────────────────────────────────────

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE_NAME}:${TAG}"
# Cloud SQL Auth Connector connection name — used for the cloudsql-instances annotation.
# DATABASE_URL uses a unix socket: ?host=/cloudsql/${CLOUDSQL_CONNECTION_NAME} (#80).
CLOUDSQL_CONNECTION_NAME="${PROJECT_ID}:${REGION}:${INSTANCE_NAME}"
SERVICE_YAML="${REPO_ROOT}/deploy/cloud-run-backend.yaml"
RENDERED_YAML="$(mktemp /tmp/cloud-run-backend-XXXXXX.yaml)"

# Ensure temp file is removed on exit (success or failure).
trap 'rm -f "${RENDERED_YAML}"' EXIT

# ── Validation ───────────────────────────────────────────────────────────────

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "ERROR: PROJECT_ID is not set. Pass --project or set GOOGLE_CLOUD_PROJECT." >&2
  exit 1
fi

# Warn when deploying with the placeholder VERCEL_URL before #127 is complete.
if [[ -z "${VERCEL_URL}" ]]; then
  echo "WARNING: VERCEL_URL is not set; using placeholder origin for CORS ALLOWED_ORIGINS." >&2
  echo "         Placeholder: https://personal-agent.vercel.app" >&2
  echo "         Set VERCEL_URL env var after the first Vercel deploy (#127) to avoid unintended CORS configuration." >&2
  VERCEL_URL="https://personal-agent.vercel.app"  # placeholder origin; update after #127
fi

# Service account created during one-time setup (see docs/cloud-run-setup.md).
CR_SA="personal-agent-backend@${PROJECT_ID}.iam.gserviceaccount.com"

echo "==> Deploying ${SERVICE_NAME}"
echo "    Project : ${PROJECT_ID}"
echo "    Region  : ${REGION}"
echo "    Image   : ${IMAGE}"
echo "    CORS    : ${VERCEL_URL}"
echo ""

# ── Step 1: Build and push container image ───────────────────────────────────

echo "==> Building Docker image..."
docker build \
  --platform linux/amd64 \
  --tag "${IMAGE}" \
  "${REPO_ROOT}"

echo "==> Pushing image to Artifact Registry..."
docker push "${IMAGE}"

# ── Step 2: Render service YAML with substituted values ─────────────────────

echo "==> Rendering service YAML..."
sed \
  -e "s|\${REGION}|${REGION}|g" \
  -e "s|\${IMAGE}|${IMAGE}|g" \
  -e "s|\${CLOUDSQL_CONNECTION_NAME}|${CLOUDSQL_CONNECTION_NAME}|g" \
  -e "s|\${CR_SA}|${CR_SA}|g" \
  -e "s|\${VERCEL_URL}|${VERCEL_URL}|g" \
  "${SERVICE_YAML}" > "${RENDERED_YAML}"

# ── Step 3: Deploy to Cloud Run ──────────────────────────────────────────────

echo "==> Deploying to Cloud Run (region: ${REGION})..."
gcloud run services replace "${RENDERED_YAML}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}"

# Allow unauthenticated HTTP invocations; access control is enforced by the
# bearer-token middleware inside the service (AGENT_API_KEY). See DEPLOYMENT.md §5.
echo "==> Allowing unauthenticated invocations (bearer-token auth enforced in-app)..."
gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --member="allUsers" \
  --role="roles/run.invoker"

# ── Step 4: Report the service URL ──────────────────────────────────────────

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --format="value(status.url)")"

echo ""
echo "==> Deploy complete."
echo ""
echo "    Service URL : ${SERVICE_URL}"
echo ""
echo "Next steps:"
echo "  1. Record this URL — Vercel (#127) needs it as private API_BASE_URL:"
echo "     ${SERVICE_URL}"
echo "  2. Set private Vercel env vars API_BASE_URL=${SERVICE_URL} and AGENT_API_KEY=<token>."
echo "  3. After the first Vercel deploy, set VERCEL_URL and re-run to apply correct CORS."
echo "  4. In Google Cloud Console, add the Gmail OAuth redirect URI (#129):"
echo "       ${SERVICE_URL}/api/v1/gmail/callback"
echo "     (If needed, add your Vercel URL under \"Authorized JavaScript origins\", not as a redirect URI.)"
