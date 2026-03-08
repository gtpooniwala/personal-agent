#!/usr/bin/env python3
"""Unit tests for slot-management helpers."""

from __future__ import annotations

import unittest

from scripts import worktree_slots


class WorktreeSlotHelpersTest(unittest.TestCase):
    def test_sanitize_slug_normalizes_text(self) -> None:
        self.assertEqual(worktree_slots.sanitize_slug("Tool Routing"), "tool-routing")
        self.assertEqual(worktree_slots.sanitize_slug("  API + SSE  "), "api-sse")

    def test_parse_branch_extracts_repo_contract_parts(self) -> None:
        parsed = worktree_slots.parse_branch("codex/chore/59-worktree-slot-manager")
        self.assertEqual(parsed["agent"], "codex")
        self.assertEqual(parsed["type"], "chore")
        self.assertEqual(parsed["issue"], "59")
        self.assertEqual(parsed["slug"], "worktree-slot-manager")

    def test_slot_sort_key_orders_stable_before_dynamic(self) -> None:
        slot_ids = ["dyn-06", "slot-02", "slot-01", "dyn-05"]
        self.assertEqual(sorted(slot_ids, key=worktree_slots.slot_sort_key), ["slot-01", "slot-02", "dyn-05", "dyn-06"])

    def test_format_shell_quotes_values(self) -> None:
        rendered = worktree_slots.format_shell({"slot_path": "/tmp/slot 01", "branch": "codex/chore/59-sample"})
        self.assertIn("slot_path='/tmp/slot 01'", rendered)
        self.assertIn("branch=codex/chore/59-sample", rendered)


if __name__ == "__main__":
    unittest.main()
