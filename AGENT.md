# AGENT.md

Canonical workflow contract for AI coding agents in this repository.

## Scope
- This is the source of truth for git/worktree/PR workflow policy.
- `docs/AGENT.md` is technical architecture documentation, not workflow policy.

## Mandatory Git Process
1. Never commit directly to `main`.
2. Never do active feature work in the `main` worktree.
3. Always create a dedicated worktree and branch for each issue or task.
4. Branch prefixes:
   - `codex/` for Codex work
   - `claude/` for Claude work
5. Push feature branches only; do not push feature commits to `main`.
6. Open PRs targeting `main`.
7. Reference and close relevant issues from PR descriptions (`Closes #<id>`).
8. Rebase on `origin/main`:
   - before starting work
   - before pushing
   - before opening or updating a PR
9. Merge using **Squash and merge** only.

## Worktree Commands
- Sync main:
  - `scripts/sync_main.sh`
- Create a new Codex worktree:
  - `scripts/new_worktree.sh codex <type> <issue> <slug>`
- Create a new Claude worktree:
  - `scripts/new_worktree.sh claude <type> <issue> <slug>`

## Standard Branch + PR Flow
1. Start from an up-to-date `origin/main`.
2. Create and switch into a dedicated worktree.
3. Make changes and commit on the feature branch.
4. Push the feature branch:
   - `git push -u origin <branch-name>`
5. Open a PR to `main`:
   - `gh pr create --base main --head <branch-name> ...`
6. Keep rebasing on `origin/main` until merge.

## CI/Policy
- Required checks:
  - `CI / tests-and-repo-checks`
  - `PR Policy / enforce-pr-policy`
- Do not merge if required checks fail.
- CI runs unit tests and deterministic repository checks.
- Run local LLM/workflow evals when orchestration, prompting, or tool-calling behavior changes, and summarize results in the PR.
