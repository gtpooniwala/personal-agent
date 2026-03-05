# AGENTS.md

Repository workflow contract for Codex.

## Mandatory Git Process
1. Never commit directly to `main`.
2. Always create a dedicated branch and worktree for each feature/fix.
3. Branch prefix for Codex: `codex/`.
4. Use granular commits.
5. Open PRs to `main` only.
6. Ensure PR references and closes the relevant issue (`Closes #<id>`).
7. Rebase on latest `origin/main`:
   - before starting work
   - before pushing
   - before opening/updating PR
8. Merge via **Squash and merge** only.

## Commands
- New worktree:
  - `scripts/new_worktree.sh codex <type> <issue> <slug>`
- Sync with main:
  - `scripts/sync_main.sh`

## CI/Policy
- Required checks:
  - `CI / test-and-eval`
  - `PR Policy / enforce-pr-policy`
- Do not merge if checks fail.
