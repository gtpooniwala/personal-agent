# Tests And Repository Checks

This directory contains automated tests and deterministic repository checks.

## Run Standard Local Checks

```bash
scripts/run_local_checks.sh
```

This command installs backend dependencies into `.venv`, runs guarded unit tests, and then runs deterministic repository checks.
By default it uses `TEST_DATABASE_URL` (or a safe PostgreSQL test DB default) for DB-backed tests.

## Run Guarded Unit Tests Only

```bash
python3 tests/run_unit_tests.py
```

`tests/run_unit_tests.py` returns non-pass when:
- no tests are discovered
- all discovered tests are skipped
- standard unittest failures/errors occur

Optional (with `pytest` installed):

```bash
pytest tests -q
```

## Run Scenario Test Script

`tests/test_comprehensive.py` is a scenario-style test script that runs multi-query behavior checks and writes `test_results.json`.

```bash
python tests/test_comprehensive.py
```

## Run Repository Checks

`tests/run_repo_checks.py` performs deterministic repository checks for core invariants.

```bash
python tests/run_repo_checks.py
```

It writes a machine-readable report to `tests/repo_checks/results.json` (local artifact, gitignored).

## Run LLM/Workflow Evals

`tests/run_llm_evals.py` runs model/workflow eval suites (separate from repo checks).

Deterministic mock mode:

```bash
python3 tests/run_llm_evals.py --mode mock --set core
```

Live orchestrator/model mode:

```bash
python3 tests/run_llm_evals.py --mode live --set core
```

It writes machine-readable reports to `tests/llm_evals/results/`.
For live runs, the harness automatically re-execs into `.venv` when the system `python3` lacks backend dependencies.
When using the Docker Compose Postgres service, set `TEST_DATABASE_URL` / `EVAL_DATABASE_URL` to full PostgreSQL DSNs that use `127.0.0.1:5433` as the host port, for example `postgresql+psycopg://personal_agent:personal_agent@127.0.0.1:5433/personal_agent_test`.
If the provider key is missing, or if `EVAL_DATABASE_URL` / `TEST_DATABASE_URL` does not point to a dedicated PostgreSQL `*_test` database, live mode exits with a clear `blocked` message.
Use `--set extended` for broader scenario coverage and `--set all` to run both core and extended cases together.

## Notes

- Some tests require project dependencies from `backend/requirements.txt`.
- Integration-heavy tests are skipped automatically if required dependencies are unavailable.
- The test suite focuses on:
  - API route behavior
  - Tool behavior
  - Tool registry behavior
  - Database operations
  - LLM config shape
