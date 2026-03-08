# AGENTS.md

Canonical workflow contract for coding agents in this repository.

## Root Checkout Rule
- The shared root checkout is control-plane/admin-only.
- If `git rev-parse --show-toplevel` equals the parent of `git rev-parse --git-common-dir`, stop before editing.
- From the shared root checkout, only do control-plane actions such as:
  - `scripts/agent-status.sh`
  - `scripts/claim-slot.sh`
  - `scripts/start-agent.sh`
  - `scripts/release-slot.sh`
  - `scripts/reclaim-stale-slots.sh`
  - `git fetch`, `git worktree list`, or other read-only inspection
- Do not implement, commit, or run feature work from the shared root checkout.

## Mandatory Contract
1. Never commit directly to `main`.
2. Never do active feature work in the shared root checkout.
3. Use the managed slot workflow for normal agent work:
   - Preferred launch: `scripts/start-agent.sh <agent> --issue <id> --type <type> --label <label>`
   - Resume parked work: `scripts/start-agent.sh <agent> --branch <branch>`
4. Branch naming must follow `<agent>/<type>/<issue>-<slug>`:
   - Codex: `codex/<type>/<issue>-<slug>`
   - Claude: `claude/<type>/<issue>-<slug>`
5. Stable managed slots are:
   - `.worktrees/slot-01`
   - `.worktrees/slot-02`
   - `.worktrees/slot-03`
   - `.worktrees/slot-04`
6. Overflow slots are allowed only through the slot manager and only up to the configured max.
7. Slot state is owned by scripts under `.worktrees/state/`. Agents must not treat issue/PR state as authoritative slot ownership.
8. Push feature branches only; do not push feature commits to `main`.
9. Open PRs targeting `main`.
10. Reference relevant issues from PR descriptions (`Refs #<id>` at minimum); use closing keywords only when the PR fully completes the issue.
11. Rebase on `origin/main` before push and before opening/updating a PR.
12. Merge using **Squash and merge** only.
13. Keep issue `#59` open as the permanent workflow/process tracker. Workflow policy PRs should include `Refs #59`.
14. Follow [`docs/ISSUE_MANAGEMENT.md`](docs/ISSUE_MANAGEMENT.md) when creating or relabeling issues.

## Required Checks
- `CI / tests-and-repo-checks`
- `PR Policy / enforce-pr-policy`

## Required Commands
- Slot status: `scripts/agent-status.sh`
- Claim without launch: `scripts/claim-slot.sh --agent <codex|claude> ...`
- Start agent in a managed slot: `scripts/start-agent.sh <codex|claude> ...`
- Release a slot: `scripts/release-slot.sh --slot <slot-id> [--keep-branch]`
- Conservative cleanup: `scripts/reclaim-stale-slots.sh [--dry-run]`
- Sync with main: `scripts/sync_main.sh`
- Sync repo-managed skills into Codex home: `scripts/sync_skills.sh`
- Automated code review: `cubic review --base main`

## Notes
- Issue and PR status are advisory cleanup hints only; they are not authoritative slot ownership signals.
- If you are already running inside a managed slot, continue working there instead of claiming a second slot for the same branch.
