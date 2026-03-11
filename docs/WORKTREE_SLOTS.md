# Worktree Slot Workflow

Last updated: March 10, 2026

This repository uses a script-owned slot/lease system for local coding-agent work.

Codex Desktop worktrees under `~/.codex/worktrees/...` are separate from this slot manager. They already count as isolated checkouts and must not use `scripts/start-agent.sh` or `scripts/claim-slot.sh`.

## Why
- The shared root checkout is a control plane, not a feature-work tree.
- Agents should not be responsible for marking worktrees free or deciding whether a slot is safe to reuse.
- Issue and PR state are useful cleanup hints, but they are not authoritative slot ownership signals.

## Slot Layout
- Stable reusable slots:
  - `.worktrees/slot-01`
  - `.worktrees/slot-02`
  - `.worktrees/slot-03`
  - `.worktrees/slot-04`
- Overflow slots:
  - `.worktrees/dyn-05`
  - `.worktrees/dyn-06`
  - and so on, up to the configured max
- Script-owned lease metadata:
  - `.worktrees/state/<slot-id>.json`

## Lease Rules
- Source of truth is the lease file managed by scripts.
- Slots move through:
  - `free`
  - `reserved`
  - `stale`
- Reserved slots stay reserved until a human explicitly releases them or a cleanup script reclaims them when it is clearly safe.
- Issue/PR status may appear in status output as hints only.
- Dirty or ambiguous worktrees are never reclaimed automatically.
- A free slot is expected to be a clean managed worktree parked in detached `HEAD` at the current `origin/main` or `main` base commit.

## Standard Commands

### Inspect status
```bash
scripts/agent-status.sh
```

### Claim without launching
```bash
scripts/claim-slot.sh --agent codex --issue 59 --type chore --label "workflow hardening"
```

Use this only as a human control-plane command from the shared root checkout for CLI / slot-managed launches. If an agent is already running in a managed worktree, or if you are inside a Codex Desktop worktree, do not call `scripts/claim-slot.sh`.

### Start Codex CLI in a managed slot
```bash
scripts/start-agent.sh codex --issue 59 --type chore --label "workflow hardening"
```

### Start Claude in a managed slot
```bash
scripts/start-agent.sh claude --issue 59 --type chore --label "workflow hardening"
```

### Start OpenCode in a managed slot
```bash
scripts/start-agent.sh opencode --issue 59 --type chore --label "workflow hardening"
```

### Resume a parked branch
```bash
scripts/start-agent.sh codex --branch codex/chore/59-workflow-hardening
```

### Release a slot when it is safe
```bash
scripts/release-slot.sh --slot slot-02
```

Releasing a slot now parks that worktree in detached `HEAD` at the current main base commit and marks the lease free. Managed slots are reused instead of removed.

Without a slot argument, `release-slot.sh` falls back to the same conservative reclaim flow as `reclaim-stale-slots.sh`:
```bash
scripts/release-slot.sh
```

If you want to make the full-slot sweep explicit, use `--all`:
```bash
scripts/release-slot.sh --all
scripts/reclaim-stale-slots.sh --all
```

Keep an unmerged branch for later reuse:
```bash
scripts/release-slot.sh --slot slot-02 --keep-branch
```

### Conservative stale inspection / reclaim
```bash
scripts/reclaim-stale-slots.sh --dry-run
scripts/reclaim-stale-slots.sh
```

## Codex App Workflow
1. Open the repository in Codex Desktop and let the app create or reuse its own isolated worktree under `~/.codex/worktrees/...`.
2. From inside that Codex Desktop worktree, create the branch directly with git:
   - `git switch -c codex/<type>/<issue>-<slug> main`
3. Do not run `scripts/start-agent.sh` or `scripts/claim-slot.sh` from inside the Codex Desktop worktree.

## OpenCode Workflow
1. Start from the shared root checkout.
2. Run `scripts/start-agent.sh opencode --issue <id> --type <type> --label <label>`.
3. The launcher claims a slot, creates or reuses the parked slot worktree, checks out the requested branch, updates the lease, and starts OpenCode in that slot.

## Managed CLI Workflow
1. Start from the shared root checkout.
2. Run `scripts/start-agent.sh <agent> ...` for Codex CLI, Claude, or OpenCode.
3. The launcher claims a slot, creates or reattaches the branch/worktree, or reuses a clean slot already parked in detached `HEAD` at the main base commit, updates the lease, and starts the requested agent in that slot.
4. Interact directly with the worker session in that terminal.

## Capacity Rules
- Four stable slots are always available for normal use.
- Overflow slots are created only when all stable slots are occupied.
- Overflow growth is bounded by `WORKTREE_SLOT_MAX` (default: `8` total slots).
- When capacity is exhausted, the allocator fails loudly and points you to `scripts/agent-status.sh`.

## Stale And Cleanup Heuristics
Status and cleanup commands may consider:
- clean vs dirty worktree
- whether the branch appears merged into `main`
- whether the lease looks old and inactive
- open PR hints when `gh` is available

These are hints, not ownership signals.

## Migration Notes
- Existing branch-named worktrees under `.worktrees/` can coexist during migration.
- The slot tools report unmanaged worktrees in status output so they are visible during cleanup.
- New shared-root / CLI work must use the slot launchers; Codex Desktop uses its own app-managed worktrees instead.
