## Summary
- What changed?
- Why?

## Linked Issue
Refs #
- Use `Closes #<id>` only when this PR fully completes the issue.

## Validation
- [ ] `python -m unittest discover -s tests -p "test_*.py" -v`
- [ ] `python tests/run_repo_checks.py`
- [ ] If this PR changes LLM/tool-calling behavior or agent workflow logic, run local eval(s) and include commands/results in PR description

## Workflow Checklist
- [ ] Branch created via worktree (not `main`)
- [ ] Rebasing done against latest `origin/main` before push/PR
- [ ] Commits are granular and focused
- [ ] CI checks pass
- [ ] Merge method will be **Squash and merge**
