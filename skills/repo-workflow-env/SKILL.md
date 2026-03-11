---
name: repo-workflow-env
description: "Use for start-of-task repository workflow setup: confirm issue scope, choose the correct isolated checkout path (managed slot for Codex CLI/Claude/OpenCode or app-created worktree for Codex Desktop), verify the issue-backed branch naming contract, and enforce rebase checkpoints."
metadata:
  short-description: Start repo workflow safely
---

# Repo Workflow Environment

Use this skill when starting implementation work in this repository.

## Non-negotiable contract
- Never work directly on `main`.
- Treat the shared root checkout as control-plane only.
- Use an isolated checkout/branch for each issue/task.
- Codex CLI, Claude, and OpenCode use the managed slot workflow from the shared root checkout.
- Codex Desktop uses its own worktree under `~/.codex/worktrees/...` and must not call `scripts/start-agent.sh` or `scripts/claim-slot.sh`.
- Branch must match `<agent>/<type>/<issue>-<slug>`.
- New work requires a target issue number before claiming a slot; do not invent issue-less scratch branches.
- Rebase on latest `origin/main` before work, before push, and before PR update.

## Workflow
1. Confirm issue and scope.
- Ensure there is a target issue number for the branch.
- If no issue exists yet, stop setup and use `repo-issue-flow` to create or refine one first.

2. Start from latest `main`.
- Run `scripts/sync_main.sh` from an existing feature branch when needed.

3. Choose the correct isolated-checkout path.
- For Codex CLI, Claude, and OpenCode from the shared root checkout:
  - Run `scripts/start-agent.sh <agent> --issue <issue> --type <type> --label <label>`.
  - If resuming parked work, run `scripts/start-agent.sh <agent> --branch <branch>`.
  - Work only inside the claimed slot under `.worktrees/slot-XX` or `.worktrees/dyn-XX`.
- For Codex Desktop:
  - Use the app-created worktree under `~/.codex/worktrees/...`.
  - Create the branch directly with git inside that worktree.
  - Do not run `scripts/start-agent.sh` or `scripts/claim-slot.sh`.
- Do not create a scratch branch that bypasses the issue-backed branch contract.

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
