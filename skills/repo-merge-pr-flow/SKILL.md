---
name: repo-merge-pr-flow
description: Use when merging a ready pull request in this repository; verify required checks, squash-merge safely, and release the current managed worktree slot after the merge when running from one.
metadata:
  short-description: Merge ready PRs and free managed slots
---

# Repo Merge PR Flow

Use this skill when the user asks to merge a PR or says a branch is ready to land.

## Non-negotiable contract
- Merge target must be `main`.
- Merge method is `Squash and merge` only.
- Do not merge until required checks are green:
  - `CI / tests-and-repo-checks`
  - `PR Policy / enforce-pr-policy`
- If the current checkout root is one of the repo-managed slot paths under `.worktrees/slot-XX` or `.worktrees/dyn-XX`, release that slot after the merge succeeds.
- Workflow-policy PRs must reference `#59` but must not close it.

## Workflow
1. Inspect the PR.
- Prefer the current branch PR:
  - `gh pr view --json number,state,baseRefName,headRefName,url`
- If the user names a PR explicitly, inspect that PR instead.
- Confirm the PR is open, targets `main`, and the head branch still matches the repo branch contract.

2. Verify merge readiness.
- Check required statuses with:
  - `gh pr checks <pr>`
- Stop if required checks are pending or failing.
- If repo policy or GitHub reports the branch is out of date with `main`, stop and rebase/update first.
- Make sure there are no local changes that still need to be committed before merging.

3. Detect whether the current checkout is a managed slot.
- Use the checkout root, not the current shell directory:
  - `repo_root="$(git rev-parse --show-toplevel)"`
  - `shared_root="$(git rev-parse --git-common-dir)"`
  - `shared_root="$(cd "$(dirname "$shared_root")/.." && pwd -P)"`
  - `managed_root="$shared_root/.worktrees"`
  - `slot_id="$(basename "$repo_root")"`
- Treat it as a managed slot only when both conditions hold:
  - `slot_id` matches `^(slot|dyn)-[0-9]{2}$`
  - `repo_root` is exactly `"$managed_root/$slot_id"`
- If either check fails, treat the checkout as non-slot-managed and skip release.

4. Merge.
- Default path:
  - `gh pr merge <pr> --squash --delete-branch`
- If `gh pr merge` fails because the checked-out local branch/worktree cannot be deleted, fall back to the GitHub merge API:
  - `gh api -X PUT repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/pulls/<pr>/merge -f merge_method=squash`
- After the API fallback, delete the remote head branch separately if it still exists:
  - `git push origin --delete <head-branch>`

5. Release the slot when applicable.
- Only do this after the merge has succeeded.
- If the checkout passed the managed-slot path check, run:
  - `scripts/release-slot.sh --slot "$slot_id"`
- If the checkout is not a managed slot, skip release.
- If slot release fails, report that separately from the merge result; the PR may already be merged.

## Output expectations
- Report the PR number and URL that were merged.
- Report whether the merge used the normal CLI path or the API fallback.
- Report whether slot release was performed, skipped, or failed.
