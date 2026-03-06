---
name: gh-address-comments
description: Triage and resolve open PR comments end-to-end using gh CLI by classifying each comment (fix now, discuss, defer with issue, or no action), applying the required action, and only resolving threads after disposition and follow-through.
metadata:
  short-description: Triage and resolve PR comments
---

# PR Comment Triage And Resolution

Use this skill when the user asks to process PR comments/review threads and drive them to a final disposition.
Run all `gh` commands with elevated network access.

Prereq:
- Ensure `gh` is authenticated (`gh auth status`).
- If unauthenticated, ask the user to run `gh auth login` and retry.

## Non-negotiable rules
- Do not resolve any thread before deciding disposition and taking the required action.
- Human and bot reviewers have the same priority.
- For large refactors, do not implement in the current PR unless the user explicitly approves; defer via issue.
- Final goal is resolution of each thread with a clear rationale.

## Workflow
1. Fetch all open PR comments and review threads.
- Run: `python "<path-to-skill>/scripts/fetch_comments.py"`
- Focus on unresolved review threads first, then actionable top-level comments.

2. Classify each item into one disposition.
- `fix-now`: important and within current PR scope.
- `discuss-with-user`: calls out an intentional choice, or confidence is low/uncertain.
- `defer-with-issue`: important but out of scope for this PR.
- `no-action`: pedantic or inconsequential.

3. Execute by disposition.
- `fix-now`:
  - Implement the fix.
  - Run relevant tests/checks.
  - Reply in thread with what changed.
  - Resolve thread.
- `discuss-with-user`:
  - Recommend a path and explain tradeoff briefly.
  - Pause for user decision before code changes.
  - After decision, act and then resolve.
- `defer-with-issue`:
  - Create a GitHub issue automatically.
  - Link the issue in the thread with a short defer rationale.
  - Resolve thread.
- `no-action`:
  - Reply with concise rationale.
  - Resolve thread automatically.

4. Report status to user.
- Provide a compact table/list: thread id, disposition, action taken, resolved state.
- Call out any remaining blocked items.

## Classification rubric
Treat as `important` when it affects:
- Correctness or data integrity
- Security/privacy
- Reliability/availability
- Significant performance behavior
- Maintainability with high regression risk
- Explicit workflow/policy contract violations

Treat as `no-action` when it is:
- Pure style preference without policy impact
- Pedantic wording/naming preference
- Micro-optimization with no practical impact

Scope rule:
- "Broader but reasonable" is allowed for nearby fixes.
- If fix expands into substantial redesign/refactor, classify `defer-with-issue` unless user explicitly approves widening scope.

## Thread resolution gate
- Review threads can be resolved via GitHub thread resolution.
- Top-level PR conversation comments do not have a resolved state; treat them as addressed after a substantive reply and include them in the status summary.

A review thread can be resolved only when one of these is true:
- Fix is merged into the PR branch and explained in-thread.
- A defer issue is created and linked in-thread.
- A no-action rationale is posted.
- A discuss item has user decision and follow-through completed.

## Useful gh operations
- Find current PR: `gh pr view --json number,url,title`
- Create defer issue: `gh issue create --title "..." --body "..."`
- Reply to PR thread/comment: use `gh api graphql` with the appropriate comment mutation.
- Resolve review thread: use `gh api graphql` `resolveReviewThread` mutation after posting disposition/action.

Notes:
- If `gh` hits auth/rate issues mid-run, ask user to re-authenticate and retry.
- Keep responses factual and concise; avoid resolving silently without rationale.
