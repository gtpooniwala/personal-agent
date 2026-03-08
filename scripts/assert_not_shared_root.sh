#!/usr/bin/env bash
set -euo pipefail

TOPLEVEL="$(git rev-parse --show-toplevel)"
if COMMON_DIR="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"; then
  :
else
  COMMON_DIR="$(git rev-parse --git-common-dir)"
  case "${COMMON_DIR}" in
    /*) ;;
    *) COMMON_DIR="$(cd "${COMMON_DIR}" && pwd -P)" ;;
  esac
fi
TOPLEVEL_REALPATH="$(cd "${TOPLEVEL}" && pwd -P)"
ROOT_CHECKOUT="$(cd "$(dirname "${COMMON_DIR}")" && pwd -P)"

if [ "${TOPLEVEL_REALPATH}" = "${ROOT_CHECKOUT}" ]; then
  echo "Shared root checkout is control-plane only."
  echo "Use scripts/start-agent.sh or scripts/claim-slot.sh to enter a managed slot before editing or committing."
  exit 1
fi
