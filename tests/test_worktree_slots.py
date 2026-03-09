#!/usr/bin/env python3
"""Unit tests for slot-management helpers."""

from __future__ import annotations

import json
import subprocess
import unittest
from tempfile import TemporaryDirectory

from scripts import worktree_slots


class WorktreeSlotHelpersTest(unittest.TestCase):
    def make_ctx(self, root: str = "/tmp/repo") -> worktree_slots.RepoContext:
        repo_root = worktree_slots.Path(root)
        return worktree_slots.RepoContext(
            cwd_root=repo_root,
            shared_root=repo_root,
            common_dir=repo_root / ".git",
            worktrees_dir=repo_root / ".worktrees",
            state_dir=repo_root / ".worktrees" / "state",
        )

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

    def test_parse_worktree_list_supports_flag_only_lines(self) -> None:
        original_git = worktree_slots.git
        worktree_slots._parse_worktree_list_cached.cache_clear()

        def fake_git(*args, **kwargs):
            return "\n".join(
                [
                    "worktree /tmp/example",
                    "HEAD abc123",
                    "detached",
                    "",
                ]
            )

        worktree_slots.git = fake_git
        try:
            ctx = worktree_slots.RepoContext(
                cwd_root=worktree_slots.Path("/tmp/repo"),
                shared_root=worktree_slots.Path("/tmp/repo"),
                common_dir=worktree_slots.Path("/tmp/repo/.git"),
                worktrees_dir=worktree_slots.Path("/tmp/repo/.worktrees"),
                state_dir=worktree_slots.Path("/tmp/repo/.worktrees/state"),
            )
            entries = worktree_slots.parse_worktree_list(ctx)
        finally:
            worktree_slots.git = original_git
            worktree_slots._parse_worktree_list_cached.cache_clear()

        self.assertEqual(entries[0]["worktree"], "/tmp/example")
        self.assertEqual(entries[0]["detached"], "true")

    def test_validate_type_rejects_invalid_values(self) -> None:
        with self.assertRaises(SystemExit):
            worktree_slots.validate_type("Bad Type")

    def test_validate_max_slots_rejects_values_below_stable_set(self) -> None:
        with self.assertRaises(SystemExit):
            worktree_slots.validate_max_slots(3)

    def test_command_exists_rejects_invalid_names(self) -> None:
        self.assertFalse(worktree_slots.command_exists(""))
        self.assertFalse(worktree_slots.command_exists("bad name"))

    def test_known_max_slots_honors_existing_overflow_leases(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = worktree_slots.Path(tmpdir)
            ctx = worktree_slots.RepoContext(
                cwd_root=root,
                shared_root=root,
                common_dir=root / ".git",
                worktrees_dir=root / ".worktrees",
                state_dir=root / ".worktrees" / "state",
            )
            ctx.state_dir.mkdir(parents=True)
            (ctx.state_dir / "dyn-10.json").write_text("{}", encoding="utf-8")

            self.assertEqual(worktree_slots.known_max_slots(ctx, worktree_slots.DEFAULT_MAX_SLOTS), 10)

    def test_observe_slot_treats_unknown_dirty_state_as_unsafe(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = worktree_slots.Path(tmpdir)
            ctx = worktree_slots.RepoContext(
                cwd_root=root,
                shared_root=root,
                common_dir=root / ".git",
                worktrees_dir=root / ".worktrees",
                state_dir=root / ".worktrees" / "state",
            )
            slot_dir = ctx.worktrees_dir / "slot-01"
            slot_dir.mkdir(parents=True)
            lease = worktree_slots.blank_lease(ctx, "slot-01")
            lease["state"] = "reserved"

            original_branch_worktree_map = worktree_slots.branch_worktree_map
            original_path_worktree_map = worktree_slots.path_worktree_map
            original_git_status_dirty = worktree_slots.git_status_dirty
            try:
                worktree_slots.branch_worktree_map = lambda _ctx: {}
                worktree_slots.path_worktree_map = lambda _ctx: {}

                def boom(_path):
                    raise RuntimeError("status unavailable")

                worktree_slots.git_status_dirty = boom
                observed = worktree_slots.observe_slot(ctx, lease, stale_hours=72)
            finally:
                worktree_slots.branch_worktree_map = original_branch_worktree_map
                worktree_slots.path_worktree_map = original_path_worktree_map
                worktree_slots.git_status_dirty = original_git_status_dirty

            self.assertTrue(observed["slot_path_exists"])
            self.assertTrue(observed["dirty"])

    def test_clear_worktree_list_cache_invalidates_cached_entries(self) -> None:
        original_git = worktree_slots.git
        calls = []

        def fake_git(*args, **kwargs):
            calls.append(args)
            return "worktree /tmp/example\nHEAD abc123\n\n"

        worktree_slots.git = fake_git
        try:
            ctx = worktree_slots.RepoContext(
                cwd_root=worktree_slots.Path("/tmp/repo"),
                shared_root=worktree_slots.Path("/tmp/repo"),
                common_dir=worktree_slots.Path("/tmp/repo/.git"),
                worktrees_dir=worktree_slots.Path("/tmp/repo/.worktrees"),
                state_dir=worktree_slots.Path("/tmp/repo/.worktrees/state"),
            )
            worktree_slots.parse_worktree_list(ctx)
            worktree_slots.parse_worktree_list(ctx)
            self.assertEqual(len(calls), 1)

            worktree_slots.clear_worktree_list_cache(ctx)
            worktree_slots.parse_worktree_list(ctx)
            self.assertEqual(len(calls), 2)
        finally:
            worktree_slots.git = original_git
            worktree_slots._parse_worktree_list_cached.cache_clear()

    def test_branch_merged_into_main_uses_merged_pr_state_when_ancestry_check_fails(self) -> None:
        ctx = self.make_ctx()
        branch = "codex/fix/59-slot-release"
        original_local_branch_exists = worktree_slots.local_branch_exists
        original_base_ref = worktree_slots.base_ref
        original_run = worktree_slots.run
        original_command_exists = worktree_slots.command_exists
        worktree_slots.cached_branch_pr_info.cache_clear()

        def fake_run(*args, **kwargs):
            if args[:3] == ("git", "merge-base", "--is-ancestor"):
                return subprocess.CompletedProcess(args, 1, "", "")
            if args[:3] == ("gh", "pr", "view"):
                payload = {
                    "number": 17,
                    "state": "MERGED",
                    "url": "https://example.test/pull/17",
                    "mergeCommit": {"oid": "deadbeef"},
                }
                return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
            raise AssertionError(f"unexpected command: {args}")

        try:
            worktree_slots.local_branch_exists = lambda _ctx, _branch: True
            worktree_slots.base_ref = lambda _ctx: "origin/main"
            worktree_slots.command_exists = lambda name: name == "gh"
            worktree_slots.run = fake_run

            self.assertTrue(worktree_slots.branch_merged_into_main(ctx, branch))
            self.assertEqual(
                worktree_slots.branch_open_pr_hint(ctx, branch),
                "PR #17 merged (https://example.test/pull/17)",
            )
        finally:
            worktree_slots.local_branch_exists = original_local_branch_exists
            worktree_slots.base_ref = original_base_ref
            worktree_slots.run = original_run
            worktree_slots.command_exists = original_command_exists
            worktree_slots.cached_branch_pr_info.cache_clear()

    def test_branch_merged_into_main_keeps_unmerged_pr_as_unmerged(self) -> None:
        ctx = self.make_ctx("/tmp/repo-closed-pr")
        branch = "codex/fix/59-slot-release"
        original_local_branch_exists = worktree_slots.local_branch_exists
        original_base_ref = worktree_slots.base_ref
        original_run = worktree_slots.run
        original_command_exists = worktree_slots.command_exists
        worktree_slots.cached_branch_pr_info.cache_clear()

        def fake_run(*args, **kwargs):
            if args[:3] == ("git", "merge-base", "--is-ancestor"):
                return subprocess.CompletedProcess(args, 1, "", "")
            if args[:3] == ("gh", "pr", "view"):
                payload = {
                    "number": 18,
                    "state": "CLOSED",
                    "url": "https://example.test/pull/18",
                    "mergeCommit": None,
                }
                return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
            raise AssertionError(f"unexpected command: {args}")

        try:
            worktree_slots.local_branch_exists = lambda _ctx, _branch: True
            worktree_slots.base_ref = lambda _ctx: "origin/main"
            worktree_slots.command_exists = lambda name: name == "gh"
            worktree_slots.run = fake_run

            self.assertFalse(worktree_slots.branch_merged_into_main(ctx, branch))
        finally:
            worktree_slots.local_branch_exists = original_local_branch_exists
            worktree_slots.base_ref = original_base_ref
            worktree_slots.run = original_run
            worktree_slots.command_exists = original_command_exists
            worktree_slots.cached_branch_pr_info.cache_clear()


if __name__ == "__main__":
    unittest.main()
