#!/usr/bin/env bash
set -euo pipefail

TOPLEVEL="$(git rev-parse --show-toplevel)"
COMMON_DIR="$(git rev-parse --git-common-dir)"
ROOT_CHECKOUT="$(cd "$(dirname "${COMMON_DIR}")" && pwd)"

if [ "${TOPLEVEL}" = "${ROOT_CHECKOUT}" ]; then
  echo "Shared root checkout is control-plane only."
  echo "Use scripts/start-agent.sh or scripts/claim-slot.sh to enter a managed slot before editing or committing."
  exit 1
fi
