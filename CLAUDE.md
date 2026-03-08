# CLAUDE.md

Repository workflow contract for Claude Code.

Canonical source of truth: `AGENT.md` at repository root.
If this file and `AGENT.md` diverge, follow `AGENT.md` and then reconcile this file.

## Mandatory Git Process
1. Never commit directly to `main`.
2. Always create a dedicated branch and worktree for each feature/fix.
3. Branch prefix for Claude: `claude/`.
4. Use granular commits.
5. Open PRs to `main` only.
6. Ensure PR references and closes the relevant issue (`Closes #<id>`).
7. Rebase on latest `origin/main`:
   - before starting work
   - before pushing
   - before opening/updating PR
8. Merge via **Squash and merge** only.

## Commands
- Automated code review (run before merging): `cubic review --base main` (or `cubic review --base` to auto-detect base branch). Repeat until no issues remain.
- New worktree:
  - `scripts/new_worktree.sh claude <type> <issue> <slug>`
- Sync with main:
  - `scripts/sync_main.sh`

## CI/Policy
- Required checks:
  - `CI / tests-and-repo-checks`
  - `PR Policy / enforce-pr-policy`
- Do not merge if checks fail.
- CI runs unit tests and deterministic repository checks only.
- Run LLM/workflow evals locally only when changes can impact LLM/tool-calling behavior or agent workflows; summarize results in the PR.
