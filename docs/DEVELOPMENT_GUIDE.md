# Development Guide

This file is the practical contributor workflow on top of the stricter policy in [`ENGINEERING_WORKFLOW.md`](ENGINEERING_WORKFLOW.md).

## Standard Change Flow
1. Sync with latest `origin/main`.
2. Create a dedicated worktree and branch.
3. Make the smallest focused change that moves one issue or task forward.
4. Run the smallest validation set that honestly matches the scope.
5. Update docs if behavior, status, or sequencing changed.
6. Commit, push, and open a PR that references the relevant issue.

## Worktrees And Branches
Use one worktree per active branch.

Preferred command:
```bash
scripts/new_worktree.sh codex docs 59 planning-refresh
```

Sync before work and before push:
```bash
scripts/sync_main.sh
```

## Validation Expectations

### Docs-only changes
- run repository checks if links, file references, or policy-sensitive docs changed

### Code changes
- run `scripts/run_local_checks.sh`
- add targeted unit or API tests when behavior changes

### Prompt, orchestration, or tool-routing changes
- run the relevant deterministic tests
- run `python tests/run_llm_evals.py --mode mock`
- run live evals when the behavior change is meaningful and credentials are available

### Runtime changes
- run runtime-specific tests and `python tests/run_runtime_evals.py`

## Documentation Expectations
Update docs whenever one of these changes:
- runtime behavior or architecture
- work sequencing or issue status
- setup or validation commands
- deployment or trigger assumptions

Primary status docs:
- [`WORKBOARD.md`](WORKBOARD.md)
- [`ROADMAP.md`](ROADMAP.md)

Primary implementation docs:
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`SYSTEM_FLOW.md`](SYSTEM_FLOW.md)
- [`API.md`](API.md)

If you add a new feature doc:
1. start from [`FEATURE_TEMPLATE.md`](FEATURE_TEMPLATE.md)
2. place it under `docs/features/` unless it is broader than one feature
3. link it from [`README.md`](README.md) when useful

## Review Standard
Prefer:
- small commits
- explicit issue linkage
- updated docs when behavior changed
- accurate validation notes in the PR body

Avoid:
- feature work directly on `main`
- stale status docs
- claiming validation you did not run
