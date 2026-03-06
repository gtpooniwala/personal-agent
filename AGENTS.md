# AGENTS.md

Repository workflow contract for Codex.

Canonical source of truth: `AGENT.md` at repository root.
If this file and `AGENT.md` diverge, follow `AGENT.md` and then reconcile this file.

## Mandatory Git Process
1. Never commit directly to `main`.
2. Always create a dedicated branch and worktree for each feature/fix.
3. Never do active feature work in the `main` worktree. If work starts on `main` by mistake, move it to a dedicated worktree immediately before committing.
4. Branch prefix for Codex: `codex/`.
5. Use granular commits.
6. Open PRs to `main` only.
7. Ensure PR references and closes the relevant issue (`Closes #<id>`).
8. Rebase on latest `origin/main`:
   - before starting work
   - before pushing
   - before opening/updating PR
9. Merge via **Squash and merge** only.

## Commands
- New worktree:
  - `scripts/new_worktree.sh codex <type> <issue> <slug>`
- Sync with main:
  - `scripts/sync_main.sh`

## CI/Policy
- Required checks:
  - `CI / tests-and-repo-checks`
  - `PR Policy / enforce-pr-policy`
- Do not merge if checks fail.
- CI runs unit tests and deterministic repository checks only.
- Run LLM/workflow evals locally only when changes can impact LLM/tool-calling behavior or agent workflows; summarize results in the PR.

## Planning Confirmation Rules
- If docs/issues disagree on scope or ordering (for example, whether `#22`/`#23` belong to the migration execution lane), stop and ask the user to confirm before implementation.
- If endpoint contract details are intentionally unspecified (for example, event pagination/cursor or cancel contract), ask the user to confirm before closing implementation work.
