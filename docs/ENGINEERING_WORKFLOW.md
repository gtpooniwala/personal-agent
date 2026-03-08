# Engineering Workflow

Last updated: March 8, 2026

## Goals
- No direct commits to `main`
- Every feature/change in a dedicated branch and managed worktree slot
- Granular commits
- PR-based merges only after review + passing CI

## Branch Rules
- Never commit directly to `main`.
- Branch naming:
  - Codex: `codex/<type>/<issue>-<slug>`
  - Claude: `claude/<type>/<issue>-<slug>`
- CI policy rejects PRs whose head branch does not match this contract.
- Examples:
  - `codex/fix/7-safe-calculator`
  - `claude/feat/16-runtime-worker`

## Worktree Rules
- The shared root checkout is control-plane/admin-only.
- Use the managed slot workflow for normal work:
  - `scripts/start-agent.sh codex --issue 7 --type fix --label "safe calculator"`
  - `scripts/start-agent.sh codex --app --issue 7 --type fix --label "safe calculator"`
- Stable reusable slots live at:
  - `.worktrees/slot-01`
  - `.worktrees/slot-02`
  - `.worktrees/slot-03`
  - `.worktrees/slot-04`
- Overflow slots are created under `.worktrees/dyn-XX` only through the slot manager.
- Lease metadata is stored under `.worktrees/state/`.
- The managed slot flow is the single supported path for new work.

Inspect / clean up:
```bash
scripts/agent-status.sh
scripts/release-slot.sh
scripts/release-slot.sh --all
scripts/reclaim-stale-slots.sh --dry-run
```

Sync before work, before push, and before opening PR:
```bash
scripts/sync_main.sh
```

## PR Rules
- Every PR must reference an issue:
  - Non-closing references are allowed for partial work: `Refs #123` / `Related to #123`
  - Use closing keywords only when fully complete: `Closes #123` / `Fixes #123`
- PRs target `main` only.
- Rebase branch on latest `origin/main` before push and before PR update.
- PR branch history must remain linear (no merge commits).
- Merge strategy is `Squash and merge` only.
- Do not merge until:
  - Required CI checks pass
  - Approval is provided per repo settings

## Issue Rules
- GitHub issues are the source of truth for individual work items.
- Follow [`ISSUE_MANAGEMENT.md`](ISSUE_MANAGEMENT.md) for issue shape, label taxonomy, and lifecycle rules.
- Prefer one issue per shippable slice; use tracker issues only for intentionally decomposed multi-PR programs.
- Use the GitHub issue forms under [`.github/ISSUE_TEMPLATE`](../.github/ISSUE_TEMPLATE) for new issues.
- Managed issue labels (`priority:*`, `size:*`, `type:*`, `track:*`) are synchronized from issue-form fields by [`.github/workflows/issue_label_sync.yml`](../.github/workflows/issue_label_sync.yml).
- Keep `WORKBOARD.md` aligned with active execution state and `ROADMAP.md` aligned with grouped planning work.

## Solo Maintainer Note
- GitHub does not count self-approval as an approving review in the usual protected-branch flow.
- For a solo repo, use:
  - PR required
  - Required checks required
  - Up-to-date branch required
  - Approvals optional (`0`) unless you use a second reviewer account

## Cross-Agent Review
- Codex and Claude can review each other by reviewing the PR diff.
- Use labels:
  - `agent:codex`
  - `agent:claude`
  - `needs-agent-review`

## Required CI Checks
- `CI / tests-and-repo-checks`
- `PR Policy / enforce-pr-policy`

CI runs unit tests and deterministic repository checks only. LLM/workflow evals are local and should be run when a change can affect LLM/tool-calling behavior or agent workflows.

## Setup Commands
1. Install hooks:
```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit .githooks/pre-push
```

2. Configure branch protection (requires repo admin via `gh`):
```bash
scripts/setup_branch_protection.sh
```

3. Sync repo-managed skills into Codex home:
```bash
scripts/sync_skills.sh
```

## Skills And Ownership
- Repository source of truth for workflow skills lives in `skills/`.
- Runtime skill location is `${CODEX_HOME:-$HOME/.codex}/skills/`.
- Sync from repository to runtime with `scripts/sync_skills.sh`.
- Current workflow skills:
  - `repo-workflow-env`: managed slot launch and rebase checkpoints
  - `repo-issue-flow`: issue creation, body normalization, and labeling
  - `repo-commit-pr-flow`: commit slicing, push/PR workflow, final checklist
  - `gh-address-comments`: triage and resolve PR comments/threads
  - `gh-fix-ci`: investigate and fix failing GitHub Actions checks
