# Tests And Evals

This directory contains automated tests and a larger scenario-style evaluation script.

## Run Unit Tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Recommended (with `pytest` installed):

```bash
pytest tests -q
```

## Run Scenario Eval

`tests/test_comprehensive.py` is an eval-style script that runs multi-query behavior checks and writes `test_results.json`.

```bash
python tests/test_comprehensive.py
```

## Run Repository Cleanup Eval

`tests/run_eval.py` is a deterministic static eval that checks core production-readiness cleanup invariants.

```bash
python tests/run_eval.py
```

It writes a machine-readable report to `tests/evals/results.json`.

## Notes

- Some tests require project dependencies from `backend/requirements.txt`.
- Integration-heavy tests are skipped automatically if required dependencies are unavailable.
- The test suite focuses on:
  - API route behavior
  - Tool behavior
  - Tool registry behavior
  - Database operations
  - LLM config shape
