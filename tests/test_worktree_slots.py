#!/usr/bin/env python3
"""Unit tests for slot-management helpers."""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import unittest
from contextlib import nullcontext
from tempfile import TemporaryDirectory
from unittest.mock import patch

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

    def test_parse_branch_accepts_opencode_prefix(self) -> None:
        parsed = worktree_slots.parse_branch("opencode/chore/59-worktree-slot-manager")
        self.assertEqual(parsed["agent"], "opencode")

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
            original_worktree_entry_for_path = worktree_slots.worktree_entry_for_path
            original_git_status_dirty = worktree_slots.git_status_dirty
            try:
                worktree_slots.branch_worktree_map = lambda _ctx: {}
                worktree_slots.worktree_entry_for_path = lambda _ctx, _path: None

                def boom(_path):
                    raise RuntimeError("status unavailable")

                worktree_slots.git_status_dirty = boom
                observed = worktree_slots.observe_slot(ctx, lease, stale_hours=72)
            finally:
                worktree_slots.branch_worktree_map = original_branch_worktree_map
                worktree_slots.worktree_entry_for_path = original_worktree_entry_for_path
                worktree_slots.git_status_dirty = original_git_status_dirty

            self.assertTrue(observed["slot_path_exists"])
            self.assertTrue(observed["dirty"])

    def test_create_or_attach_worktree_reuses_clean_parked_slot(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = worktree_slots.Path(tmpdir)
            ctx = worktree_slots.RepoContext(
                cwd_root=root,
                shared_root=root,
                common_dir=root / ".git",
                worktrees_dir=root / ".worktrees",
                state_dir=root / ".worktrees" / "state",
            )
            target = ctx.worktrees_dir / "slot-01"
            target.mkdir(parents=True)

            original_branch_worktree_map = worktree_slots.branch_worktree_map
            original_worktree_entry_for_path = worktree_slots.worktree_entry_for_path
            original_is_parked_entry = worktree_slots.is_parked_entry
            original_git_status_dirty = worktree_slots.git_status_dirty
            original_ensure_branch_checked_out = worktree_slots.ensure_branch_checked_out
            original_link_shared_credentials = worktree_slots.link_shared_credentials
            calls: list[tuple[str, str]] = []

            try:
                worktree_slots.branch_worktree_map = lambda _ctx: {}
                worktree_slots.worktree_entry_for_path = lambda _ctx, _path: {
                    "worktree": str(target),
                    "HEAD": "deadbeef",
                    "detached": "true",
                }
                worktree_slots.is_parked_entry = lambda _ctx, _entry: True
                worktree_slots.git_status_dirty = lambda _path: False
                worktree_slots.ensure_branch_checked_out = lambda _ctx, path, branch: calls.append((str(path), branch))
                worktree_slots.link_shared_credentials = lambda _ctx, _path: None

                worktree_slots.create_or_attach_worktree(ctx, "slot-01", "opencode/chore/59-worktree-slot-manager")
            finally:
                worktree_slots.branch_worktree_map = original_branch_worktree_map
                worktree_slots.worktree_entry_for_path = original_worktree_entry_for_path
                worktree_slots.is_parked_entry = original_is_parked_entry
                worktree_slots.git_status_dirty = original_git_status_dirty
                worktree_slots.ensure_branch_checked_out = original_ensure_branch_checked_out
                worktree_slots.link_shared_credentials = original_link_shared_credentials

            self.assertEqual(calls, [(str(target), "opencode/chore/59-worktree-slot-manager")])

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
        original_git = worktree_slots.git
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
                    "headRefOid": "deadbeef",
                }
                return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
            raise AssertionError(f"unexpected command: {args}")

        try:
            worktree_slots.local_branch_exists = lambda _ctx, _branch: True
            worktree_slots.base_ref = lambda _ctx: "origin/main"
            worktree_slots.git = lambda *args, **kwargs: "deadbeef"
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
            worktree_slots.git = original_git
            worktree_slots.run = original_run
            worktree_slots.command_exists = original_command_exists
            worktree_slots.cached_branch_pr_info.cache_clear()

    def test_branch_merged_into_main_keeps_unmerged_pr_as_unmerged(self) -> None:
        ctx = self.make_ctx("/tmp/repo-closed-pr")
        branch = "codex/fix/59-slot-release"
        original_local_branch_exists = worktree_slots.local_branch_exists
        original_base_ref = worktree_slots.base_ref
        original_git = worktree_slots.git
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
                    "headRefOid": "deadbeef",
                }
                return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
            raise AssertionError(f"unexpected command: {args}")

        try:
            worktree_slots.local_branch_exists = lambda _ctx, _branch: True
            worktree_slots.base_ref = lambda _ctx: "origin/main"
            worktree_slots.git = lambda *args, **kwargs: "deadbeef"
            worktree_slots.command_exists = lambda name: name == "gh"
            worktree_slots.run = fake_run

            self.assertFalse(worktree_slots.branch_merged_into_main(ctx, branch))
        finally:
            worktree_slots.local_branch_exists = original_local_branch_exists
            worktree_slots.base_ref = original_base_ref
            worktree_slots.git = original_git
            worktree_slots.run = original_run
            worktree_slots.command_exists = original_command_exists
            worktree_slots.cached_branch_pr_info.cache_clear()

    def test_branch_merged_into_main_rejects_merged_pr_when_branch_tip_has_advanced(self) -> None:
        ctx = self.make_ctx("/tmp/repo-advanced-branch")
        branch = "codex/fix/59-slot-release"
        original_local_branch_exists = worktree_slots.local_branch_exists
        original_base_ref = worktree_slots.base_ref
        original_git = worktree_slots.git
        original_run = worktree_slots.run
        original_command_exists = worktree_slots.command_exists
        worktree_slots.cached_branch_pr_info.cache_clear()

        def fake_run(*args, **kwargs):
            if args[:3] == ("git", "merge-base", "--is-ancestor"):
                return subprocess.CompletedProcess(args, 1, "", "")
            if args[:3] == ("gh", "pr", "view"):
                payload = {
                    "number": 19,
                    "state": "MERGED",
                    "url": "https://example.test/pull/19",
                    "headRefOid": "mergedsha",
                }
                return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")
            raise AssertionError(f"unexpected command: {args}")

        try:
            worktree_slots.local_branch_exists = lambda _ctx, _branch: True
            worktree_slots.base_ref = lambda _ctx: "origin/main"
            worktree_slots.git = lambda *args, **kwargs: "currentsha"
            worktree_slots.command_exists = lambda name: name == "gh"
            worktree_slots.run = fake_run

            self.assertFalse(worktree_slots.branch_merged_into_main(ctx, branch))
        finally:
            worktree_slots.local_branch_exists = original_local_branch_exists
            worktree_slots.base_ref = original_base_ref
            worktree_slots.git = original_git
            worktree_slots.run = original_run
            worktree_slots.command_exists = original_command_exists
            worktree_slots.cached_branch_pr_info.cache_clear()

    def test_release_attention_items_report_expected_anomalies(self) -> None:
        rows = [
            {"slot_id": "slot-01", "dirty": True, "checked_out_branch": None, "is_parked": True, "state": "free", "merged": None, "branch": None},
            {
                "slot_id": "slot-02",
                "dirty": True,
                "checked_out_branch": "opencode/chore/59-worktree-slot-manager",
                "is_parked": False,
                "state": "reserved",
                "merged": False,
                "branch": "opencode/chore/59-worktree-slot-manager",
            },
            {
                "slot_id": "slot-03",
                "dirty": False,
                "checked_out_branch": "codex/fix/59-slot-release",
                "is_parked": False,
                "state": "reserved",
                "merged": True,
                "branch": "codex/fix/59-slot-release",
            },
        ]

        items = worktree_slots.release_attention_items(rows)

        self.assertEqual(len(items), 3)
        self.assertIn("parked at main base commit but has uncommitted files", items[0])
        self.assertIn("has uncommitted files", items[1])
        self.assertIn("appears merged, but the slot is still reserved", items[2])

    def test_cmd_release_reports_dirty_slot_and_status_summary(self) -> None:
        ctx = self.make_ctx("/tmp/repo-release-dirty")
        lease = {"slot_id": "slot-01", "state": "reserved", "branch": "codex/fix/59-slot-release"}
        original_repo_context = worktree_slots.repo_context
        original_ensure_dirs = worktree_slots.ensure_dirs
        original_validate_slot_id = worktree_slots.validate_slot_id
        original_known_max_slots = worktree_slots.known_max_slots
        original_state_lock = worktree_slots.state_lock
        original_load_lease = worktree_slots.load_lease
        original_observe_slot = worktree_slots.observe_slot
        original_print_release_status_summary = worktree_slots.print_release_status_summary
        stderr = io.StringIO()

        try:
            worktree_slots.repo_context = lambda: ctx
            worktree_slots.ensure_dirs = lambda _ctx: None
            worktree_slots.validate_slot_id = lambda slot_id, _max_slots: slot_id
            worktree_slots.known_max_slots = lambda _ctx, _configured_max: 4
            worktree_slots.state_lock = lambda _ctx: nullcontext()
            worktree_slots.load_lease = lambda _ctx, _slot_id: dict(lease)
            worktree_slots.observe_slot = lambda _ctx, _lease, _stale_hours: {
                "slot_path_exists": True,
                "dirty": True,
                "merged": False,
                "checked_out_branch": "codex/fix/59-slot-release",
            }
            worktree_slots.print_release_status_summary = lambda _ctx, _stale_hours, stream=None: print(
                "status-summary", file=stream
            )

            with patch("sys.stderr", stderr):
                result = worktree_slots.cmd_release(argparse.Namespace(slot="slot-01", keep_branch=False, stale_hours=72))
        finally:
            worktree_slots.repo_context = original_repo_context
            worktree_slots.ensure_dirs = original_ensure_dirs
            worktree_slots.validate_slot_id = original_validate_slot_id
            worktree_slots.known_max_slots = original_known_max_slots
            worktree_slots.state_lock = original_state_lock
            worktree_slots.load_lease = original_load_lease
            worktree_slots.observe_slot = original_observe_slot
            worktree_slots.print_release_status_summary = original_print_release_status_summary

        self.assertEqual(result, 1)
        self.assertIn("Release failed for slot-01", stderr.getvalue())
        self.assertIn("status-summary", stderr.getvalue())

    def test_cmd_reclaim_parks_clean_slot_instead_of_removing_worktree(self) -> None:
        ctx = self.make_ctx("/tmp/repo-reclaim")
        lease = {"slot_id": "slot-01", "state": "reserved", "branch": "codex/fix/59-slot-release"}
        original_repo_context = worktree_slots.repo_context
        original_ensure_dirs = worktree_slots.ensure_dirs
        original_known_max_slots = worktree_slots.known_max_slots
        original_state_lock = worktree_slots.state_lock
        original_known_slot_ids = worktree_slots.known_slot_ids
        original_load_lease = worktree_slots.load_lease
        original_observe_slot = worktree_slots.observe_slot
        original_park_slot_worktree = worktree_slots.park_slot_worktree
        original_mark_free = worktree_slots.mark_free
        stdout = io.StringIO()
        parked: list[str] = []
        freed: list[str] = []

        try:
            worktree_slots.repo_context = lambda: ctx
            worktree_slots.ensure_dirs = lambda _ctx: None
            worktree_slots.known_max_slots = lambda _ctx, _configured_max: 4
            worktree_slots.state_lock = lambda _ctx: nullcontext()
            worktree_slots.known_slot_ids = lambda _ctx, _max_slots: ["slot-01"]
            worktree_slots.load_lease = lambda _ctx, _slot_id: dict(lease)
            worktree_slots.observe_slot = lambda _ctx, _lease, _stale_hours: {
                "safe_to_reclaim": True,
                "checked_out_branch": "codex/fix/59-slot-release",
                "is_parked": False,
                "slot_path_exists": True,
                "stale_reasons": [],
            }
            worktree_slots.park_slot_worktree = lambda _ctx, slot_id: parked.append(slot_id)
            worktree_slots.mark_free = lambda _ctx, slot_id: freed.append(slot_id)

            with patch("sys.stdout", stdout):
                result = worktree_slots.cmd_reclaim(
                    argparse.Namespace(all=False, dry_run=False, json=False, max_slots=8, stale_hours=72)
                )
        finally:
            worktree_slots.repo_context = original_repo_context
            worktree_slots.ensure_dirs = original_ensure_dirs
            worktree_slots.known_max_slots = original_known_max_slots
            worktree_slots.state_lock = original_state_lock
            worktree_slots.known_slot_ids = original_known_slot_ids
            worktree_slots.load_lease = original_load_lease
            worktree_slots.observe_slot = original_observe_slot
            worktree_slots.park_slot_worktree = original_park_slot_worktree
            worktree_slots.mark_free = original_mark_free

        self.assertEqual(result, 0)
        self.assertEqual(parked, ["slot-01"])
        self.assertEqual(freed, ["slot-01"])


if __name__ == "__main__":
    unittest.main()
