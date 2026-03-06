#!/usr/bin/env bash
set -euo pipefail

BRANCH="$(git rev-parse --abbrev-ref HEAD)"

if [ "$BRANCH" = "main" ]; then
  echo "Do not work directly on main. Switch to a feature branch."
  exit 1
fi

git fetch origin main
git rebase origin/main

echo "Rebased ${BRANCH} onto origin/main"
