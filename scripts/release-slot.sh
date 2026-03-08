#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [ "$#" -eq 0 ]; then
  exec "${PYTHON_BIN}" "${ROOT_DIR}/scripts/worktree_slots.py" reclaim-stale
fi

for arg in "$@"; do
  if [ "${arg}" = "--all" ]; then
    exec "${PYTHON_BIN}" "${ROOT_DIR}/scripts/worktree_slots.py" reclaim-stale "$@"
  fi
done

exec "${PYTHON_BIN}" "${ROOT_DIR}/scripts/worktree_slots.py" release "$@"
