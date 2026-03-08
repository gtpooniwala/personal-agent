# Test Results Summary

This file is intentionally no longer a frozen count-based snapshot. Those go stale quickly. Use this as a short checklist for what to report after validation.

## What To Record
For each PR, note:
- exact commands run
- whether they passed, failed, or were blocked
- any important scope gaps

## Common Validation Sets

### Docs Or Workflow Change
```bash
python tests/run_repo_checks.py
```

### General Backend Change
```bash
scripts/run_local_checks.sh
```

### Runtime Change
```bash
.venv/bin/python -m unittest tests.test_runtime_service -v
.venv/bin/python -m unittest tests.test_api_runtime_responsiveness -v
python tests/run_runtime_evals.py
```

### Prompt Or Tool-Calling Change
```bash
python tests/run_llm_evals.py --mode mock
python tests/run_llm_evals.py --mode live
```

## Recent Important Additions
- Runtime responsiveness checks matter because the `#51` migration step explicitly moved blocking orchestration off the FastAPI event loop.
- Runtime evals are the best place to catch lifecycle, retry, and responsiveness regressions that ordinary unit tests may miss.

## Source Of Truth
- Validation workflow: [`TESTING.md`](TESTING.md)
- Execution status: [`WORKBOARD.md`](WORKBOARD.md)
- Runtime rationale: [`MIGRATION_RUNTIME_ARCHITECTURE.md`](MIGRATION_RUNTIME_ARCHITECTURE.md)
