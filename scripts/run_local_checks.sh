#!/usr/bin/env bash
set -euo pipefail

if { [ ! -f "AGENT.md" ] && [ ! -f "AGENTS.md" ]; } || [ ! -d "backend" ] || [ ! -d "tests" ]; then
  echo "Run this script from the repository root or a managed worktree root."
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
TEST_DB_URL="${TEST_DATABASE_URL:-postgresql+psycopg://personal_agent:personal_agent@127.0.0.1:5433/personal_agent_test}"
export TEST_DATABASE_URL="${TEST_DB_URL}"
export DATABASE_URL="${TEST_DB_URL}"
"${VENV_PY}" - <<'PY'
import os
from sqlalchemy.engine import make_url
import psycopg
from psycopg import sql

test_url = make_url(os.environ["TEST_DATABASE_URL"])
test_db = test_url.database
admin_url = test_url.set(database="postgres")
admin_dsn = admin_url.render_as_string(hide_password=False).replace("postgresql+psycopg://", "postgresql://", 1)

with psycopg.connect(admin_dsn, autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (test_db,))
        if cur.fetchone() is None:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(test_db)))
PY
"${VENV_PY}" tests/run_unit_tests.py

echo "Running deterministic repository checks..."
"${VENV_PY}" tests/run_repo_checks.py

echo "Local checks completed successfully."
