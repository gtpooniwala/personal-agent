# Workboard

Last updated: March 5, 2026

## How This Is Used
This file is the AI execution board for this repo.

Workflow:
1. Pick the top item from `Now`.
2. Implement in a small, stable change.
3. Run tests/eval relevant to the change.
4. Commit and push.
5. Update GitHub issue and move the item state in this file.

## Status Legend
- `todo`
- `in_progress`
- `blocked`
- `done`

## Now
- [ ] `todo` Replace calculator `eval` with safe parser/evaluator (Issue: `TBD`)
- [ ] `todo` Fix upload error path referencing uninitialized `document_id` (Issue: `TBD`)
- [ ] `todo` Remove XSS-prone `innerHTML` rendering in chat/conversation/document UIs (Issue: `TBD`)
- [ ] `todo` Isolate orchestrator state per request/session boundary (Issue: `TBD`)

## Next
- [ ] `todo` Add dependency profile for reliable local test execution (`dev` requirements / make target) (Issue: `TBD`)
- [ ] `todo` Add behavioral evals for tool selection and RAG relevance regressions (Issue: `TBD`)
- [ ] `todo` Make Gmail tool optional in active tool list unless configured (Issue: `TBD`)

## Later
- [ ] `todo` Add auth + multi-user tenancy (Issue: `TBD`)
- [ ] `todo` Migrate vector retrieval to managed/vector DB option (Issue: `TBD`)
- [ ] `todo` Add observability for latency, token, and tool call metrics (Issue: `TBD`)

## Done
- [x] `done` Legacy module cleanup + import hygiene baseline eval
- [x] `done` README architecture/setup refresh

## Notes
- Keep items small enough to land in one commit when possible.
- Prefer one GitHub issue per item, linked directly above.
