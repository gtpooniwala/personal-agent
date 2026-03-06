# Tests And Repository Checks

This directory contains automated tests and deterministic repository checks.

## Run Unit Tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Recommended (with `pytest` installed):

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
python tests/run_llm_evals.py --mode mock
```

Live orchestrator/model mode:

```bash
python tests/run_llm_evals.py --mode live
```

It writes machine-readable reports to `tests/llm_evals/results/`.
If the provider key is missing, live mode exits with a clear `blocked` message explaining which API key to set.

## Notes

- Some tests require project dependencies from `backend/requirements.txt`.
- Integration-heavy tests are skipped automatically if required dependencies are unavailable.
- The test suite focuses on:
  - API route behavior
  - Tool behavior
  - Tool registry behavior
  - Database operations
  - LLM config shape
