#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-gtpooniwala/personal-agent}"
GITHUB_ACTIONS_APP_ID=15368

echo "Configuring branch protection for ${REPO} main..."

PAYLOAD_FILE="$(mktemp)"
trap 'rm -f "${PAYLOAD_FILE}"' EXIT
cat > "${PAYLOAD_FILE}" <<EOF
{
  "required_status_checks": {
    "strict": true,
    "checks": [
      {"context": "tests-and-repo-checks", "app_id": ${GITHUB_ACTIONS_APP_ID}},
      {"context": "enforce-pr-policy", "app_id": ${GITHUB_ACTIONS_APP_ID}}
    ]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": false,
    "required_approving_review_count": 0
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": false,
  "lock_branch": false,
  "allow_fork_syncing": true
}
EOF

gh api -X PUT "repos/${REPO}/branches/main/protection" \
  -H "Accept: application/vnd.github+json" \
  --input "${PAYLOAD_FILE}"

echo "Configuring merge strategy (squash-only) for ${REPO}..."

gh api -X PATCH "repos/${REPO}" \
  -H "Accept: application/vnd.github+json" \
  -F "allow_squash_merge=true" \
  -F "allow_merge_commit=false" \
  -F "allow_rebase_merge=false" \
  -F "delete_branch_on_merge=true"

echo "Branch protection applied."
