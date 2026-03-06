#!/usr/bin/env bash
set -euo pipefail

if [ ! -f "AGENT.md" ] || [ ! -d "backend" ] || [ ! -d "tests" ]; then
  echo "Run this script from the repository root."
  exit 1
fi

VENV_DIR=".venv"
VENV_PY="${VENV_DIR}/bin/python"

if [ ! -x "${VENV_PY}" ]; then
  echo "Creating virtual environment at ${VENV_DIR}"
  python3 -m venv "${VENV_DIR}"
fi

echo "Installing backend dependencies..."
"${VENV_PY}" -m pip install --upgrade pip
"${VENV_PY}" -m pip install -r backend/requirements.txt

echo "Running guarded unit tests..."
"${VENV_PY}" tests/run_unit_tests.py

echo "Running deterministic repository checks..."
"${VENV_PY}" tests/run_repo_checks.py

echo "Local checks completed successfully."
