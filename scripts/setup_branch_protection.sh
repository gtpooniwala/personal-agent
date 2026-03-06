#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-gtpooniwala/personal-agent}"

echo "Configuring branch protection for ${REPO} main..."

gh api -X PUT "repos/${REPO}/branches/main/protection" \
  -H "Accept: application/vnd.github+json" \
  -F "required_status_checks[strict]=true" \
  -f "required_status_checks[contexts][]=CI / tests-and-repo-checks" \
  -f "required_status_checks[contexts][]=PR Policy / enforce-pr-policy" \
  -F "enforce_admins=true" \
  -F "required_pull_request_reviews[dismiss_stale_reviews]=true" \
  -F "required_pull_request_reviews[require_code_owner_reviews]=false" \
  -F "required_pull_request_reviews[required_approving_review_count]=0" \
  -F "restrictions=null" \
  -F "required_linear_history=true" \
  -F "allow_force_pushes=false" \
  -F "allow_deletions=false" \
  -F "block_creations=false" \
  -F "required_conversation_resolution=false" \
  -F "lock_branch=false" \
  -F "allow_fork_syncing=true"

echo "Configuring merge strategy (squash-only) for ${REPO}..."

gh api -X PATCH "repos/${REPO}" \
  -H "Accept: application/vnd.github+json" \
  -F "allow_squash_merge=true" \
  -F "allow_merge_commit=false" \
  -F "allow_rebase_merge=false" \
  -F "delete_branch_on_merge=true"

echo "Branch protection applied."
