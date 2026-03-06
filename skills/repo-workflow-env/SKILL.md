---
name: repo-workflow-env
description: Use for start-of-task repository workflow setup: pick issue scope, create branch/worktree via project scripts, verify branch naming contract, and enforce rebase checkpoints.
metadata:
  short-description: Start worktree workflow safely
---

# Repo Workflow Environment

Use this skill when starting implementation work in this repository.

## Non-negotiable contract
- Never work directly on `main`.
- Use a dedicated branch/worktree for each issue/task.
- Branch must match `<agent>/<type>/<issue>-<slug>`.
- Rebase on latest `origin/main` before work, before push, and before PR update.

## Workflow
1. Confirm issue and scope.
- Ensure there is a target issue number for the branch.

2. Start from latest `main`.
- Run `scripts/sync_main.sh` from an existing feature branch when needed.

3. Create branch + worktree.
- Run `scripts/new_worktree.sh codex <type> <issue> <slug>` for Codex work.
- Work only inside the newly created `.worktrees/...` directory.

4. Verify environment.
- Confirm branch name and worktree path.
- Confirm `core.hooksPath` points to `.githooks`.

5. Rebase checkpoints.
- Run `scripts/sync_main.sh` before push.
- Run `scripts/sync_main.sh` before opening/updating a PR.

## Output expectations
- Report the created branch and worktree path.
- Report any blocking policy mismatch before code changes.
