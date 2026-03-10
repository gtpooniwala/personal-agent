#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <agent:codex|claude|opencode> [--app|--cli] [slot claim args]"
  exit 1
fi

AGENT="$1"
shift

MODE="cli"
FORWARD_ARGS=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --app)
      MODE="app"
      ;;
    --cli)
      MODE="cli"
      ;;
    --mode|--format)
      echo "$1 is managed by scripts/start-agent.sh and cannot be forwarded."
      exit 1
      ;;
    --mode=*|--format=*)
      echo "${1%%=*} is managed by scripts/start-agent.sh and cannot be forwarded."
      exit 1
      ;;
    *)
      FORWARD_ARGS+=("$1")
      ;;
  esac
  shift
done

if [[ "${AGENT}" != "codex" && "${AGENT}" != "claude" && "${AGENT}" != "opencode" ]]; then
  echo "Agent must be 'codex', 'claude', or 'opencode'."
  exit 1
fi

if [[ "${AGENT}" == "claude" && "${MODE}" == "app" ]]; then
  echo "Claude app mode is not supported by this launcher. Use CLI mode instead."
  exit 1
fi

if [[ "${AGENT}" == "opencode" && "${MODE}" == "app" ]]; then
  echo "OpenCode app mode is not supported by this launcher. Use CLI mode instead."
  exit 1
fi

ROOT_DIR="$(git rev-parse --show-toplevel)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! CLAIM_JSON="$("${PYTHON_BIN}" "${ROOT_DIR}/scripts/worktree_slots.py" claim --agent "${AGENT}" --mode "${MODE}" --format json "${FORWARD_ARGS[@]}")"; then
  echo "Failed to prepare a managed slot for ${AGENT}. Review the error above and fix that issue first." >&2
  exit 1
fi
CLAIM_FIELDS=()
while IFS= read -r line; do
  CLAIM_FIELDS+=("${line}")
done < <(
  printf '%s\n' "${CLAIM_JSON}" | "${PYTHON_BIN}" -c '
import json
import sys

payload = json.load(sys.stdin)
print(payload["slot_id"])
print(payload["slot_path"])
print(payload["branch"])
'
)

slot_id="${CLAIM_FIELDS[0]}"
slot_path="${CLAIM_FIELDS[1]}"
branch="${CLAIM_FIELDS[2]}"

echo "Claimed ${slot_id} at ${slot_path} on branch ${branch}"

if [[ "${AGENT}" == "codex" && "${MODE}" == "cli" ]]; then
  exec codex -C "${slot_path}"
fi

if [[ "${AGENT}" == "codex" && "${MODE}" == "app" ]]; then
  exec codex app "${slot_path}"
fi

if [[ "${AGENT}" == "opencode" && "${MODE}" == "cli" ]]; then
  cd "${slot_path}"
  exec opencode
fi

cd "${slot_path}"

# Activate the base repo's venv so all slots share a consistent Python environment.
# This ensures dev tools (pytest, etc.) installed in the canonical venv are always
# available regardless of which per-worktree venv may be on $PATH.
VENV="${ROOT_DIR}/.venv"
if [[ -f "${VENV}/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "${VENV}/bin/activate"
  echo "Activated Python venv: ${VENV}"
else
  echo "Warning: base repo venv not found at ${VENV}; using system Python" >&2
fi

exec claude
