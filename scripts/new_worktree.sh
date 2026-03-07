#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 4 ]; then
  echo "Usage: $0 <agent:codex|claude> <type> <issue-number> <slug>"
  exit 1
fi

AGENT="$1"
TYPE="$2"
ISSUE="$3"
SLUG="$4"
ROOT_DIR="$(git rev-parse --show-toplevel)"

if [[ "$AGENT" != "codex" && "$AGENT" != "claude" ]]; then
  echo "Agent must be 'codex' or 'claude'."
  exit 1
fi

if ! [[ "$ISSUE" =~ ^[0-9]+$ ]]; then
  echo "Issue number must be numeric."
  exit 1
fi

# Restrict free-form path/branch components to safe characters only.
# This prevents path traversal and unexpected branch structures.
if ! [[ "$TYPE" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "Type must match: ^[a-z0-9][a-z0-9-]*$"
  exit 1
fi

if ! [[ "$SLUG" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "Slug must match: ^[a-z0-9][a-z0-9-]*$"
  exit 1
fi

cd "${ROOT_DIR}"
git fetch origin main

BRANCH="${AGENT}/${TYPE}/${ISSUE}-${SLUG}"
WT_PATH=".worktrees/${AGENT}-${TYPE}-${ISSUE}-${SLUG}"

if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
  echo "Branch ${BRANCH} already exists."
  exit 1
fi

if git ls-remote --exit-code --heads origin "${BRANCH}" >/dev/null 2>&1; then
  echo "Remote branch origin/${BRANCH} already exists."
  exit 1
fi

mkdir -p .worktrees
git worktree add "${WT_PATH}" -b "${BRANCH}" origin/main

credential_candidates=(
  ".env"
  ".env.local"
  ".env.development.local"
  ".env.test.local"
  ".env.production.local"
  ".npmrc"
  ".pypirc"
  ".netrc"
  "backend/data/gmail/client_secret.json"
  "backend/data/gmail/token.pickle"
)

for credential_file in "${credential_candidates[@]}"; do
  if [ -f "${credential_file}" ] && [ ! -e "${WT_PATH}/${credential_file}" ] && [ ! -L "${WT_PATH}/${credential_file}" ]; then
    mkdir -p "$(dirname "${WT_PATH}/${credential_file}")"
    ln -s "${ROOT_DIR}/${credential_file}" "${WT_PATH}/${credential_file}"
  fi
done

echo "Created worktree: ${WT_PATH}"
echo "Branch: ${BRANCH}"
