#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SOURCE_ROOT="${REPO_ROOT}/skills"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
DEST_ROOT="${CODEX_HOME_DIR}/skills"
CLAUDE_HOME_DIR="${CLAUDE_HOME:-$HOME/.claude}"
CLAUDE_DEST_ROOT="${CLAUDE_HOME_DIR}/skills"

DRY_RUN=0
ONLY_SKILL=""

usage() {
  echo "Usage: $0 [--dry-run] [--only <skill-name>]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --only)
      if [[ $# -lt 2 ]]; then
        usage
        exit 1
      fi
      ONLY_SKILL="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ ! -d "${SOURCE_ROOT}" ]]; then
  echo "Source skills directory does not exist: ${SOURCE_ROOT}"
  exit 1
fi

if [[ -z "${CODEX_HOME_DIR}" || "${CODEX_HOME_DIR}" == "/" ]]; then
  echo "Refusing to continue because CODEX_HOME resolves to an unsafe path: ${CODEX_HOME_DIR}"
  exit 1
fi

if [[ -z "${DEST_ROOT}" || "${DEST_ROOT}" == "/" || "${DEST_ROOT}" == "//" ]]; then
  echo "Refusing to continue because DEST_ROOT is unsafe: ${DEST_ROOT}"
  exit 1
fi

if [[ -z "${CLAUDE_HOME_DIR}" || "${CLAUDE_HOME_DIR}" == "/" ]]; then
  echo "Refusing to continue because CLAUDE_HOME resolves to an unsafe path: ${CLAUDE_HOME_DIR}"
  exit 1
fi

if [[ -z "${CLAUDE_DEST_ROOT}" || "${CLAUDE_DEST_ROOT}" == "/" || "${CLAUDE_DEST_ROOT}" == "//" ]]; then
  echo "Refusing to continue because CLAUDE_DEST_ROOT is unsafe: ${CLAUDE_DEST_ROOT}"
  exit 1
fi

mkdir -p "${DEST_ROOT}"
mkdir -p "${CLAUDE_DEST_ROOT}"

validate_skill_name() {
  local skill_name="$1"
  if [[ ! "${skill_name}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
    echo "Invalid skill name: ${skill_name}"
    echo "Skill names may contain only letters, digits, '.', '_' and '-' (no path separators)."
    exit 1
  fi
}

sync_one() {
  local skill_name="$1"
  local dst_root="$2"
  local dst="${dst_root}/${skill_name}"
  validate_skill_name "${skill_name}"

  local src="${SOURCE_ROOT}/${skill_name}"
  local src_real=""
  local dst_parent_real=""
  local dst_real=""

  if [[ ! -d "${src}" ]]; then
    echo "Skill not found in repo: ${skill_name}"
    exit 1
  fi

  if [[ ${DRY_RUN} -eq 1 ]]; then
    echo "[dry-run] sync ${src} -> ${dst}"
    return
  fi

  case "${dst}" in
    "${dst_root}/"*) ;;
    *)
      echo "Refusing to remove unexpected destination path: ${dst}"
      exit 1
      ;;
  esac

  src_real="$(cd "${src}" && pwd -P)"
  dst_parent_real="$(cd "$(dirname "${dst}")" && pwd -P)"
  dst_real="${dst_parent_real}/$(basename "${dst}")"
  if [[ "${src_real}" == "${dst_real}" || "${src_real}" == "${dst_real}/"* || "${dst_real}" == "${src_real}/"* ]]; then
    echo "Refusing to sync because source and destination overlap: ${src_real} <-> ${dst_real}"
    exit 1
  fi

  rm -rf "${dst}"
  cp -R "${src}" "${dst}"
  echo "Synced ${skill_name} -> ${dst}"
}

if [[ -n "${ONLY_SKILL}" ]]; then
  sync_one "${ONLY_SKILL}" "${DEST_ROOT}"
  sync_one "${ONLY_SKILL}" "${CLAUDE_DEST_ROOT}"
  exit 0
fi

shopt -s nullglob
for path in "${SOURCE_ROOT}"/*; do
  if [[ -d "${path}" ]]; then
    skill="$(basename "${path}")"
    sync_one "${skill}" "${DEST_ROOT}"
    sync_one "${skill}" "${CLAUDE_DEST_ROOT}"
  fi
done
