# Issue Management

Last updated: March 12, 2026

## Purpose
- Make issue creation, labeling, and execution tracking consistent across GitHub, local planning docs, and AI-agent workflows.
- Keep the system lightweight: enough structure to make backlog triage reliable, without turning issue creation into bureaucracy.

## Source Of Truth
- GitHub issues are the source of truth for individual work items.
- [`WORKBOARD.md`](WORKBOARD.md) is the source of truth for active execution sequencing.
- [`ROADMAP.md`](ROADMAP.md) is the source of truth for medium-term planning and grouped initiatives.
- Issue [#59](https://github.com/gtpooniwala/personal-agent/issues/59) is the permanent tracker for workflow/process improvements only.
- Issue [#200](https://github.com/gtpooniwala/personal-agent/issues/200) is the permanent tracker for documentation maintenance only.

## Minimum Contract
- Prefer one issue per shippable slice of work.
- Every implementation PR must reference an issue.
- Every issue should explain:
  - the problem or goal
  - the proposed scope
  - what "done" looks like
- Use a parent tracker only when the work is intentionally split across multiple PRs or sub-issues.
- Keep `WORKBOARD.md` and `ROADMAP.md` aligned when adding or materially reshaping roadmap-level work.

## Label Taxonomy

### Request Class
Use zero or one of these labels.

- `bug`: broken behavior, regression, incorrect output, or reliability defect.
- `feature request`: net-new user-facing or system capability.
- `documentation`: docs-only or docs-led work.

Internal engineering tasks do not need a request-class label if they are primarily refactors, architecture follow-ups, or operational work.

### Work Type
Use one or two `type:*` labels.

- `type:architecture`: contracts, boundaries, sequencing, data model changes, large refactors.
- `type:security`: auth, secrets, access control, vulnerability reduction, hardening.
- `type:cleanup`: simplification, dead code removal, hygiene, non-behavioral cleanup.
- `type:improvement`: correctness, resilience, UX polish, quality improvements.
- `type:ops`: deployment, CI/CD, observability, runtime operations, infra behavior.

Rules:
- One primary type is expected on almost every issue.
- A second type is allowed when the work genuinely spans both concerns.
- Avoid adding three or more type labels; that is usually a sign the issue should be decomposed.

### Priority
Use exactly one `priority:*` label.

- `priority:p0`: production-breaking defect, security risk, or work blocking core development.
- `priority:p1`: high-impact item that should be taken soon.
- `priority:p2`: normal planned work.
- `priority:p3`: backlog or future-facing work.

### Size
Use exactly one `size:*` label on normal execution issues.

- `size:S`: isolated change, usually one focused PR.
- `size:M`: moderate cross-file change, still expected to land as one coherent slice.
- `size:L`: multi-step or cross-cutting change that may need decomposition or a parent tracker.

Exceptions:
- Permanent tracker issues and meta issues may omit size when the work is intentionally unbounded.
- In this repo, issue `#59` (workflow/process) and issue `#200` (documentation maintenance) are the standing examples.

### Track
Use `track:*` labels only for long-running initiatives that cut across multiple issues.

- `track:migration`: runtime migration and follow-on work tied to that stream.

Do not create new track labels casually. A track label should represent a durable program, not a temporary theme.

### Agent Labels
- `agent:codex`, `agent:claude`, `agent:opencode`, and `needs-agent-review` are primarily PR/review labels.
- Do not use them on issues unless the issue itself is explicitly about review ownership.

## Title Guidance
- Prefer concise, problem-first titles.
- Use prefixes like `docs:` or `feat:` only when they add clarity.
- Avoid implementation-detail titles when the underlying problem can be named directly.

Good:
- `Move blocking orchestration work off event loop`
- `Define graceful shutdown behavior for orchestration executor`

Less useful:
- `Fix runtime stuff`
- `Improve backend`

## Issue Types

### Feature Request
Use when adding a capability.

Expected fields:
- summary
- user or system problem
- proposed behavior
- acceptance criteria
- labels for type, priority, and size

### Bug
Use when behavior is wrong today.

Expected fields:
- observed behavior
- expected behavior
- reproduction or evidence
- impact
- acceptance criteria
- labels for type, priority, and size

### Documentation
Use for docs-only work or ADR-like documentation tasks.

Expected fields:
- current gap
- target audience
- proposed documentation change
- acceptance criteria
- labels for type, priority, and size

### Engineering Task
Use for refactors, architecture follow-ups, operational work, or decomposition that is not well-described as a feature request or bug.

Expected fields:
- summary
- context
- proposed scope
- acceptance criteria or decision output
- labels for type, priority, and size

## Lifecycle Rules
- `Open` means the work remains actionable.
- Close an issue only when the linked change fully completes the scope.
- Use `Refs #<id>` for partial progress.
- Use `Closes/Fixes/Resolves #<id>` only when the issue is actually done.
- Keep issue `#59` open permanently.
- Keep issue `#200` open permanently.

## Implementation In This Repo
- GitHub issue forms live under [`.github/ISSUE_TEMPLATE`](../.github/ISSUE_TEMPLATE).
- Issue label synchronization is automated by [`.github/workflows/issue_label_sync.yml`](../.github/workflows/issue_label_sync.yml).
- Agent issue intake and relabeling should use the repo-local skill [`skills/repo-issue-flow/SKILL.md`](../skills/repo-issue-flow/SKILL.md).
- Periodic documentation refresh PRs can reference `#200` instead of creating throwaway doc-sync issues.

## Practical Defaults
- If you are unsure between `priority:p2` and `priority:p3`, default to `priority:p2` only when the item is already likely to be scheduled.
- If you are unsure between `size:M` and `size:L`, choose `size:L` when the issue probably needs decomposition or multiple commits/PRs.
- If the issue is about runtime contracts or boundaries, it is probably `type:architecture`.
- If it is about making existing behavior safer or more reliable, it is probably `type:improvement`.
