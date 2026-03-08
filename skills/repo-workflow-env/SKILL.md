---
name: repo-workflow-env
description: Use for start-of-task repository workflow setup: confirm issue scope, claim a managed worktree slot via project scripts, verify the issue-backed branch naming contract, and enforce rebase checkpoints.
metadata:
  short-description: Start managed slot workflow safely
---

# Repo Workflow Environment

Use this skill when starting implementation work in this repository.

## Non-negotiable contract
- Never work directly on `main`.
- Treat the shared root checkout as control-plane only.
- Use a managed slot/branch for each issue/task.
- Branch must match `<agent>/<type>/<issue>-<slug>`.
- New work requires a target issue number before claiming a slot; do not invent issue-less scratch branches.
- Rebase on latest `origin/main` before work, before push, and before PR update.

## Workflow
1. Confirm issue and scope.
- Ensure there is a target issue number for the branch.
- If no issue exists yet, stop setup and use `repo-issue-flow` to create or refine one first.

2. Start from latest `main`.
- Run `scripts/sync_main.sh` from an existing feature branch when needed.

3. Launch a managed slot.
- Run `scripts/start-agent.sh codex --issue <issue> --type <type> --label <label>` for Codex work.
- If resuming parked work, run `scripts/start-agent.sh codex --branch <branch>`.
- Work only inside the claimed slot under `.worktrees/slot-XX` or `.worktrees/dyn-XX`.
- Do not claim a new slot with a scratch branch name that bypasses the issue-backed branch contract.

4. Verify environment.
- Confirm branch name and worktree path.
- Confirm `core.hooksPath` points to `.githooks`.

5. Rebase checkpoints.
- Run `scripts/sync_main.sh` before push.
- Run `scripts/sync_main.sh` before opening/updating a PR.

## Output expectations
- Report the claimed branch and slot path.
- Report when setup is blocked on missing issue scope instead of silently creating a scratch branch.
- Report any blocking policy mismatch before code changes.
