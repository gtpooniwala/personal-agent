# Worktree Slot Workflow

Last updated: March 8, 2026

This repository uses a script-owned slot/lease system for local coding-agent work.

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

## Standard Commands

### Inspect status
```bash
scripts/agent-status.sh
```

### Claim without launching
```bash
scripts/claim-slot.sh --agent codex --issue 59 --type chore --label "workflow hardening"
```

### Start Codex CLI in a managed slot
```bash
scripts/start-agent.sh codex --issue 59 --type chore --label "workflow hardening"
```

### Start Codex app in a managed slot
```bash
scripts/start-agent.sh codex --app --issue 59 --type chore --label "workflow hardening"
```

### Start Claude in a managed slot
```bash
scripts/start-agent.sh claude --issue 59 --type chore --label "workflow hardening"
```

### Resume a parked branch
```bash
scripts/start-agent.sh codex --branch codex/chore/59-workflow-hardening
```

### Release a slot when it is safe
```bash
scripts/release-slot.sh --slot slot-02
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
1. Keep a small number of reusable slot folders.
2. Start work from the shared root checkout:
   - `scripts/start-agent.sh codex --app --issue <id> --type <type> --label <label>`
3. The launcher claims a slot, creates or reattaches the branch/worktree, updates the lease file, and opens Codex Desktop on that slot path.
4. Reuse the same stable slot paths over time instead of creating endless new app project folders.

If you prefer to open the app manually:
1. Claim a slot with `scripts/claim-slot.sh ... --mode app`
2. Open the reported slot path with `codex app <slot-path>`

## CLI Workflow
1. Start from the shared root checkout.
2. Run `scripts/start-agent.sh <agent> ...`.
3. The launcher claims a slot, creates or reattaches the branch/worktree, updates the lease, and starts the requested agent in that slot.
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
- New work must use the slot launchers; the old branch-named worktree helper has been removed.
