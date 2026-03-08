---
name: repo-issue-flow
description: Use when creating, refining, or relabeling GitHub issues in this repository; enforce the local issue-management contract, apply labels consistently, and keep issue bodies compatible with the repo's issue-form automation.
metadata:
  short-description: Create and triage repo issues
---

# Repo Issue Flow

Use this skill when the task involves creating a new issue, improving an existing issue, or normalizing issue labels in this repository.

## Non-negotiable contract
- Follow [`docs/ISSUE_MANAGEMENT.md`](../../docs/ISSUE_MANAGEMENT.md).
- Reuse the field headings from the matching issue form in [`.github/ISSUE_TEMPLATE`](../../.github/ISSUE_TEMPLATE) when creating issues with `gh`.
- Every issue should end with clear acceptance criteria or an explicit decision output.
- Apply labels using the existing taxonomy; do not invent ad hoc labels unless the user explicitly wants the taxonomy expanded.

## Workflow
1. Choose the correct issue shape.
- Prefer the closest existing issue form:
  - `feature.yml`
  - `bug.yml`
  - `documentation.yml`
  - `engineering-task.yml`

2. Inspect current state before editing.
- For existing issues, read the current body and labels with `gh issue view`.
- For new issues, check whether a related tracker or duplicate already exists.

3. Normalize the issue body.
- Keep the title concise and problem-first.
- Mirror the issue-form headings exactly so the label-sync workflow can parse them.
- Keep scope narrow enough for one shippable slice unless the issue is intentionally a tracker.

4. Apply labels.
- Ensure one `priority:*` label.
- Ensure one `size:*` label for normal execution issues.
- Ensure one or two `type:*` labels.
- Add `bug`, `feature request`, or `documentation` only when the issue matches that class.
- Add `track:*` labels only for durable cross-issue initiatives.

5. Align local planning docs when needed.
- Update `docs/WORKBOARD.md` or `docs/ROADMAP.md` only if the issue changes active execution sequencing or roadmap structure.
- Keep workflow/process work tied to issue `#59` where relevant.

## Output expectations
- Report the issue numbers created or updated.
- Report the labels applied or changed.
- Call out duplicates, tracker relationships, or planning-doc follow-ups explicitly.
