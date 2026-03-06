# Engineering Workflow

Last updated: March 5, 2026

## Goals
- No direct commits to `main`
- Every feature/change in a dedicated branch and worktree
- Granular commits
- PR-based merges only after review + passing CI

## Branch Rules
- Never commit directly to `main`.
- Branch naming:
  - Codex: `codex/<type>/<issue>-<slug>`
  - Claude: `claude/<type>/<issue>-<slug>`
- Examples:
  - `codex/fix/7-safe-calculator`
  - `claude/feat/16-runtime-worker`

## Worktree Rules
- Use one worktree per active branch.
- Recommended location: `.worktrees/<branch-name-sanitized>`.

Create:
```bash
scripts/new_worktree.sh codex fix 7 safe-calculator
```

Sync before work, before push, and before opening PR:
```bash
scripts/sync_main.sh
```

## PR Rules
- Every PR must link and close an issue using a closing keyword:
  - `Closes #123` or `Fixes #123`
- PRs target `main` only.
- Rebase branch on latest `origin/main` before push and before PR update.
- Merge strategy is `Squash and merge` only.
- Do not merge until:
  - Required CI checks pass
  - Approval is provided per repo settings

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
- `CI / test-and-eval`
- `PR Policy / enforce-pr-policy`

CI runs unit tests only. Evals are local and should be run when a change can affect LLM/tool-calling behavior or agent workflows.

## Setup Commands
1. Install hooks:
```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-push
```

2. Configure branch protection (requires repo admin via `gh`):
```bash
scripts/setup_branch_protection.sh
```
