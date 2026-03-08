#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <agent:codex|claude> [--app|--cli] [slot claim args]"
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

if [[ "${AGENT}" != "codex" && "${AGENT}" != "claude" ]]; then
  echo "Agent must be 'codex' or 'claude'."
  exit 1
fi

if [[ "${AGENT}" == "claude" && "${MODE}" == "app" ]]; then
  echo "Claude app mode is not supported by this launcher. Use CLI mode instead."
  exit 1
fi

ROOT_DIR="$(git rev-parse --show-toplevel)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

eval "$("${PYTHON_BIN}" "${ROOT_DIR}/scripts/worktree_slots.py" claim --agent "${AGENT}" --mode "${MODE}" --format shell "${FORWARD_ARGS[@]}")"

echo "Claimed ${slot_id} at ${slot_path} on branch ${branch}"

if [[ "${AGENT}" == "codex" && "${MODE}" == "cli" ]]; then
  exec codex -C "${slot_path}"
fi

if [[ "${AGENT}" == "codex" && "${MODE}" == "app" ]]; then
  exec codex app "${slot_path}"
fi

cd "${slot_path}"
exec claude
