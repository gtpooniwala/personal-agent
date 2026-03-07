---
name: repo-commit-pr-flow
description: Use when preparing commits, pushing, and opening/updating pull requests; enforce commit hygiene, required PR body fields, and policy-compliant push/PR flow.
metadata:
  short-description: Commit, push, and PR workflow
---

# Repo Commit And PR Flow

Use this skill when changes are ready to commit, push, or publish as a PR.

## Non-negotiable contract
- Keep commits granular and task-focused.
- Do not commit or push feature work from `main`; use a dedicated branch/worktree.
- Keep branch rebased on latest `origin/main`.
- PR must target `main` and include an issue reference (`Refs #<id>` minimum).
- Use closing keywords (`Closes/Fixes/Resolves #<id>`) only when the PR fully completes that issue.
- Merge strategy is squash-only.

## Workflow
1. Prepare commit set.
- Group related changes into focused commit(s).
- Exclude generated/local-noise files.

2. Validate before commit.
- Run relevant tests/checks for changed scope.
- Ensure no policy-violating files are included.
- Use `cubic cli` and `cubic mcp` to review changes against the base branch (e.g., `cubic review --base main` or `cubic review --base` for auto-detect).
- Address any issues found by `cubic` and re-run until no issues remain.

3. Commit.
- Use clear, imperative commit messages.
- Avoid mixing unrelated concerns in one commit.

4. Rebase and push.
- Run `scripts/sync_main.sh` before push.
- Push current branch to origin.

5. Open or update PR.
- Use `.github/pull_request_template.md`.
- Include issue reference in PR body (`Refs #<id>` minimum).
- Include validation commands/results, and eval results when LLM/tool-calling behavior changed.

6. Final policy checklist.
- Required checks are green:
  - `CI / tests-and-repo-checks`
  - `PR Policy / enforce-pr-policy`
  - Automated Code Review (`cubic review --base main`) passed with no issues.
- Branch is up to date with `origin/main`.
- Merge method remains squash-and-merge.

## Output expectations
- Report commits made, tests run, and PR metadata updates.
- Call out any policy blocker explicitly.
