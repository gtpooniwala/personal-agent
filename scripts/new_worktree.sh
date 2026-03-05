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

if [[ "$AGENT" != "codex" && "$AGENT" != "claude" ]]; then
  echo "Agent must be 'codex' or 'claude'."
  exit 1
fi

if ! [[ "$ISSUE" =~ ^[0-9]+$ ]]; then
  echo "Issue number must be numeric."
  exit 1
fi

git fetch origin
git checkout main
git pull --rebase origin main

BRANCH="${AGENT}/${TYPE}/${ISSUE}-${SLUG}"
WT_PATH=".worktrees/${AGENT}-${TYPE}-${ISSUE}-${SLUG}"

if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
  echo "Branch ${BRANCH} already exists."
  exit 1
fi

mkdir -p .worktrees
git worktree add "${WT_PATH}" -b "${BRANCH}" origin/main
echo "Created worktree: ${WT_PATH}"
echo "Branch: ${BRANCH}"
