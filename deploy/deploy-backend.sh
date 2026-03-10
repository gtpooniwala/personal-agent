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
# After the first Vercel deploy (#127), set VERCEL_URL below to the actual
# Vercel origin so the CORS ALLOWED_ORIGINS value is correct.

set -euo pipefail

# ── Configurable defaults ────────────────────────────────────────────────────

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${CLOUD_RUN_REGION:-us-central1}"
TAG="${1:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"

# Service / infra names — must match the values used during one-time setup.
SERVICE_NAME="personal-agent-backend"
AR_REPO="personal-agent"                       # Artifact Registry repository name
VPC_CONNECTOR_NAME="personal-agent-connector"  # VPC connector name (#80)

# Vercel frontend origin for CORS. Update after the first Vercel deploy (#127).
# Example: "https://personal-agent.vercel.app"
VERCEL_URL="${VERCEL_URL:-https://personal-agent.vercel.app}"

# Service account created during one-time setup (see docs/cloud-run-setup.md).
CR_SA="personal-agent-backend@${PROJECT_ID}.iam.gserviceaccount.com"

# ── Derived values ───────────────────────────────────────────────────────────

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE_NAME}:${TAG}"
VPC_CONNECTOR="projects/${PROJECT_ID}/locations/${REGION}/connectors/${VPC_CONNECTOR_NAME}"
SERVICE_YAML="${REPO_ROOT}/deploy/cloud-run-backend.yaml"
RENDERED_YAML="$(mktemp /tmp/cloud-run-backend-XXXXXX.yaml)"

# ── Parse args ───────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT_ID="$2"; shift 2 ;;
    --region)  REGION="$2";     shift 2 ;;
    --tag)     TAG="$2";        shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# ── Validation ───────────────────────────────────────────────────────────────

if [[ -z "${PROJECT_ID}" ]]; then
  echo "ERROR: PROJECT_ID is not set. Pass --project or set GOOGLE_CLOUD_PROJECT." >&2
  exit 1
fi

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
  -e "s|\${PROJECT_ID}|${PROJECT_ID}|g" \
  -e "s|\${REGION}|${REGION}|g" \
  -e "s|\${IMAGE}|${IMAGE}|g" \
  -e "s|\${VPC_CONNECTOR}|${VPC_CONNECTOR}|g" \
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

rm -f "${RENDERED_YAML}"

echo ""
echo "==> Deploy complete."
echo ""
echo "    Service URL : ${SERVICE_URL}"
echo ""
echo "Next steps:"
echo "  1. Record this URL — Vercel (#127) needs it as NEXT_PUBLIC_API_BASE_URL:"
echo "     ${SERVICE_URL}/api/v1"
echo "  2. Update VERCEL_URL in deploy/deploy-backend.sh once the Vercel URL is known."
echo "  3. Re-run this script after updating VERCEL_URL to apply the CORS change."
echo "  4. Add Cloud Run URL to Gmail OAuth redirect URIs (#129)."
