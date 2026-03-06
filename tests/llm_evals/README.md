# LLM Eval Harness

This folder contains local model/workflow eval suites. These are intentionally separate from deterministic repository checks in `tests/repo_checks/`.

## Run

Mock mode (deterministic, no model API required):

```bash
python tests/run_llm_evals.py --mode mock
```

Live mode (runs real orchestrator + model/tool stack):

```bash
python tests/run_llm_evals.py --mode live
```

If a provider key is missing (default: `GEMINI_API_KEY`), live mode exits as `blocked` with setup instructions.

Optional suite filter:

```bash
python tests/run_llm_evals.py --mode mock --suite tool_calling --suite workflow
```

## Case Format

Each suite file in `cases/` uses schema version `1.0` and includes:

- `suite`: suite name
- `cases[]`: list of eval cases
- `turns[]`: one or more conversation turns
- `expected`: deterministic assertions

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

- `tests/llm_evals/results/report-<mode>-<timestamp>.json`
- `tests/llm_evals/results/latest.json`

Each report contains per-case pass/fail details and aggregate summaries by suite.
