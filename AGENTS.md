# AGENTS.md

Repository workflow contract for Codex.

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
