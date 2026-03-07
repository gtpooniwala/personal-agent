# LLM Eval Harness

This folder contains local model/workflow eval suites. These are intentionally separate from deterministic repository checks in `tests/repo_checks/`.

## Run

Mock mode (deterministic, no model API required):

```bash
python tests/run_llm_evals.py --mode mock --set core
```

Live mode (runs real orchestrator + model/tool stack):

```bash
python tests/run_llm_evals.py --mode live --set core
```

Live mode requirements:

- `GEMINI_API_KEY` (or equivalent configured provider key)
- `EVAL_DATABASE_URL` or `TEST_DATABASE_URL` pointing to a dedicated PostgreSQL `*_test` database

If either prerequisite is missing, live mode exits as `blocked` with setup instructions.

Optional set and suite filters:

```bash
python tests/run_llm_evals.py --mode mock --set extended
python tests/run_llm_evals.py --mode mock --set all --suite tool_calling --suite workflow
```

## Case Format

Each suite file in `cases/` uses schema version `1.0` and includes:

- `suite`: suite name
- `cases[].set`: `core` or `extended`
- `cases[]`: list of eval cases
- `turns[]`: one or more conversation turns
- `expected`: deterministic assertions

Set intent:

- `core`: fast baseline routing/workflow coverage for routine local runs
- `extended`: broader scenario coverage, including optional/less-common paths
- `all`: union of both sets

Supported assertions:

- `per_turn[].must_call`
- `per_turn[].must_not_call`
- `per_turn[].response_contains`
- `per_turn[].response_contains_any` (at least one substring must match)
- `per_turn[].response_not_contains`
- `overall_must_call`
- `overall_must_not_call`
- `overall_response_contains`

Optional mode-specific overrides:

- `expected.by_mode.mock`
- `expected.by_mode.live`

If provided, the selected mode override replaces top-level `expected` keys with the same name.

## Reports

Reports are written to:

- `tests/llm_evals/results/report-<mode>-<set>-<timestamp>.json`
- `tests/llm_evals/results/latest.json`

Each report contains per-case pass/fail details and aggregate summaries by suite.
