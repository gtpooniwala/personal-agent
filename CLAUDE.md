# CLAUDE.md

Repository workflow contract for Claude Code.

Canonical source of truth: `AGENTS.md` at repository root.
If this file and `AGENTS.md` diverge, follow `AGENTS.md` and then reconcile this file.

## Mandatory Git Process
1. Never commit directly to `main`.
2. Never implement from the shared root checkout; use the managed slot workflow.
3. Branch prefix for Claude: `claude/`.
4. Use granular commits.
5. Open PRs to `main` only.
6. Ensure PR references and closes the relevant issue (`Closes #<id>`).
7. Rebase on latest `origin/main`:
   - before starting work
   - before pushing
   - before opening/updating PR
8. Merge via **Squash and merge** only.

## Commands
- Automated code review (run before merging): `cubic review --base main` (or `cubic review --base` to auto-detect base branch). Repeat until no issues remain.
- Launch into a managed slot:
  - `scripts/start-agent.sh claude --issue <issue> --type <type> --label <label>`
- Resume a parked branch:
  - `scripts/start-agent.sh claude --branch <branch>`
- Status / cleanup:
  - `scripts/agent-status.sh`
  - `scripts/release-slot.sh --slot <slot-id> [--keep-branch]`
  - `scripts/reclaim-stale-slots.sh --dry-run`
- Sync with main:
  - `scripts/sync_main.sh`

## CI/Policy
- Required checks:
  - `CI / tests-and-repo-checks`
  - `PR Policy / enforce-pr-policy`
- Do not merge if checks fail.
- CI runs unit tests and deterministic repository checks only.
- Run LLM/workflow evals locally only when changes can impact LLM/tool-calling behavior or agent workflows; summarize results in the PR.
