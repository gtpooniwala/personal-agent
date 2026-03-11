---
name: repo-merge-pr-flow
description: Use when merging a ready pull request in this repository; require a clean worktree, address PR comments first, run local cubic review with no remaining issues, squash-merge safely, and release the current managed worktree slot after the merge when running from one.
metadata:
  short-description: Merge ready PRs and free managed slots
---

# Repo Merge PR Flow

Use this skill when the user asks to merge a PR or says a branch is ready to land.

## Non-negotiable contract
- Merge target must be `main`.
- Merge method is `Squash and merge` only.
- This skill only proceeds when the current checkout has no uncommitted changes.
- Before merging, run local `cubic review --base main` and stop if it reports unresolved issues.
- Before merging, use the `gh-address-comments` skill and make sure all actionable PR comments and review threads are addressed and resolved.
- Do not merge until required checks are green:
  - `CI / tests-and-repo-checks`
  - `PR Policy / enforce-pr-policy`
- If the current checkout root is one of the repo-managed slot paths under `.worktrees/slot-XX` or `.worktrees/dyn-XX`, release that slot after the merge succeeds.
- Workflow-policy PRs must reference `#59` but must not close it.

## Workflow
1. Check local working tree state before any merge work.
- Run `git status --short`.
- If there are no uncommitted changes, continue.
- If there are uncommitted changes that are in scope for the current PR:
  - Switch to the `repo-commit-pr-flow` skill.
  - Commit/push/update the PR as appropriate.
  - Stop after the commit flow and wait for explicit user input before continuing with merge work.
- If there are uncommitted changes that are out of scope or their intent is unclear:
  - Do not merge.
  - Discuss the unexpected changes with the user first.

2. Inspect the PR.
- Prefer the current branch PR:
  - `gh pr view --json number,state,baseRefName,headRefName,url`
- If the user names a PR explicitly, inspect that PR instead.
- Confirm the PR is open, targets `main`, and the head branch still matches the repo branch contract.

3. Run local review before comment resolution.
- Run local `cubic review --base main`.
- Stop if cubic reports any issue that still needs action.

4. Address PR comments before checking merge readiness.
- Explicitly use the `gh-address-comments` skill.
- Make sure all actionable review threads and PR comments are addressed.
- Do not continue until review threads are resolved or there is a documented/user-approved reason an item remains open.

5. Verify merge readiness.
- Check required statuses with:
  - `gh pr checks <pr>`
- Stop if required checks are pending or failing.
- If repo policy or GitHub reports the branch is out of date with `main`, stop and rebase/update first.

6. Detect whether the current checkout is a managed slot.
- Use the checkout root, not the current shell directory:
  - `repo_root="$(git rev-parse --show-toplevel)"`
  - `shared_root="$(git rev-parse --git-common-dir)"`
  - `shared_root="$(cd "$(dirname "$shared_root")" && pwd -P)"`
  - `managed_root="$shared_root/.worktrees"`
  - `slot_id="$(basename "$repo_root")"`
- Treat it as a managed slot only when both conditions hold:
  - `slot_id` matches `^(slot|dyn)-[0-9]{2}$`
  - `repo_root` is exactly `"$managed_root/$slot_id"`
- If either check fails, treat the checkout as non-slot-managed and skip release.

7. Merge.
- Default path:
  - `gh pr merge <pr> --squash`
- Do not use `--delete-branch` from an active worktree. In this repo, the shared root normally holds `main`, so `gh pr merge --delete-branch` may try to switch the current worktree to `main` before deleting the checked-out branch and fail with a worktree-branch collision.
- After the merge succeeds, delete the remote head branch separately:
  - `git push origin --delete <head-branch>`
- If the normal CLI merge path fails for a GitHub-side reason, fall back to the GitHub merge API:
  - `gh api -X PUT repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/pulls/<pr>/merge -f merge_method=squash`
- After the API fallback, delete the remote head branch separately if it still exists:
  - `git push origin --delete <head-branch>`

8. Release the slot when applicable.
- Only do this after the merge has succeeded.
- If the checkout passed the managed-slot path check, run:
  - `scripts/release-slot.sh --slot "$slot_id"`
- The managed-slot release step will park the current worktree in detached `HEAD` at the main base commit, which is the correct local cleanup for this workflow.
- If the checkout is not a managed slot, skip release.
- For non-slot worktrees such as Codex Desktop, do not try to auto-delete the current local branch while it is checked out. If local cleanup is needed later, first switch or detach that worktree, then delete the branch from a safe checkout.
- If slot release fails, report that separately from the merge result; the PR may already be merged.

## Output expectations
- Report the PR number and URL that were merged.
- Report that PR comments were addressed/resolved before merge.
- Report whether local `cubic review --base main` passed cleanly.
- Report whether the merge used the normal CLI path or the API fallback.
- Report whether slot release was performed, skipped, or failed.
