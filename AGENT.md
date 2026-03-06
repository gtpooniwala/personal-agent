# AGENT.md

Canonical workflow contract for AI coding agents in this repository.

## Scope
- This is the source of truth for git/worktree/PR workflow policy.
- Architecture and feature docs live under `docs/` (for example, `docs/ARCHITECTURE.md` and `docs/features/`).

## Mandatory Contract
1. Never commit directly to `main`.
2. Never do active feature work in the `main` worktree.
3. Always create a dedicated worktree and branch for each issue or task.
4. Branch naming must follow `<agent>/<type>/<issue>-<slug>`:
   - Codex: `codex/<type>/<issue>-<slug>`
   - Claude: `claude/<type>/<issue>-<slug>`
5. Push feature branches only; do not push feature commits to `main`.
6. Open PRs targeting `main`.
7. Reference and close relevant issues from PR descriptions (`Closes #<id>`).
8. Rebase on `origin/main`:
   - before starting work
   - before pushing
   - before opening or updating a PR
9. Merge using **Squash and merge** only.
10. For code-change workflow tasks, apply `repo-workflow-env` and `repo-commit-pr-flow`. For PR review comments, apply `gh-address-comments`. For failing checks, apply `gh-fix-ci`.

## Required Checks
- `CI / tests-and-repo-checks`
- `PR Policy / enforce-pr-policy`

## Required Commands
- New worktree: `scripts/new_worktree.sh <agent:codex|claude> <type> <issue> <slug>`
- Sync with main: `scripts/sync_main.sh`
- Sync repo-managed skills into Codex home: `scripts/sync_skills.sh`

## Notes
- Do not merge if required checks fail.
- CI runs backend/frontend tests and deterministic repository checks.
- Run local LLM/workflow evals when orchestration, prompting, or tool-calling behavior changes, and summarize results in the PR.
