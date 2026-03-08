#!/usr/bin/env python3
"""Manage shared worktree slots for CLI and app-based coding agents."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shlex
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_STABLE_SLOTS = 4
DEFAULT_MAX_SLOTS = int(os.environ.get("WORKTREE_SLOT_MAX", "8"))
DEFAULT_STALE_HOURS = int(os.environ.get("WORKTREE_SLOT_STALE_HOURS", "72"))
ALLOWED_AGENTS = {"codex", "claude"}
ALLOWED_MODES = {"cli", "app"}
BRANCH_RE = re.compile(
    r"^(?P<agent>codex|claude)/(?P<type>[a-z0-9][a-z0-9-]*)/(?P<issue>[0-9]+)-(?P<slug>[a-z0-9][a-z0-9-]*)$"
)
SLOT_RE = re.compile(r"^(slot|dyn)-[0-9]{2}$")


@dataclass
class RepoContext:
    cwd_root: Path
    shared_root: Path
    common_dir: Path
    worktrees_dir: Path
    state_dir: Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def run(
    *args: str,
    cwd: Path | None = None,
    check: bool = True,
    capture_stderr: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=str(cwd) if cwd else None,
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if capture_stderr else subprocess.PIPE,
    )


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    proc = run("git", *args, cwd=cwd, check=check)
    return proc.stdout.strip()


def command_exists(name: str) -> bool:
    return run("sh", "-lc", f"command -v {shlex.quote(name)} >/dev/null 2>&1", check=False).returncode == 0


def repo_context() -> RepoContext:
    cwd_root = Path(git("rev-parse", "--show-toplevel")).resolve()
    common_dir = Path(git("rev-parse", "--git-common-dir"))
    if not common_dir.is_absolute():
        common_dir = (cwd_root / common_dir).resolve()
    else:
        common_dir = common_dir.resolve()
    shared_root = common_dir.parent.resolve()
    worktrees_dir = shared_root / ".worktrees"
    state_dir = worktrees_dir / "state"
    return RepoContext(
        cwd_root=cwd_root,
        shared_root=shared_root,
        common_dir=common_dir,
        worktrees_dir=worktrees_dir,
        state_dir=state_dir,
    )


def ensure_dirs(ctx: RepoContext) -> None:
    ctx.worktrees_dir.mkdir(parents=True, exist_ok=True)
    ctx.state_dir.mkdir(parents=True, exist_ok=True)


@contextmanager
def state_lock(ctx: RepoContext) -> Any:
    ensure_dirs(ctx)
    lock_path = ctx.state_dir / ".lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def stable_slot_ids() -> list[str]:
    return [f"slot-{index:02d}" for index in range(1, DEFAULT_STABLE_SLOTS + 1)]


def dynamic_slot_ids(max_slots: int) -> list[str]:
    return [f"dyn-{index:02d}" for index in range(DEFAULT_STABLE_SLOTS + 1, max_slots + 1)]


def all_slot_ids(max_slots: int) -> list[str]:
    return stable_slot_ids() + dynamic_slot_ids(max_slots)


def slot_path(ctx: RepoContext, slot_id: str) -> Path:
    return ctx.worktrees_dir / slot_id


def lease_path(ctx: RepoContext, slot_id: str) -> Path:
    return ctx.state_dir / f"{slot_id}.json"


def blank_lease(ctx: RepoContext, slot_id: str) -> dict[str, Any]:
    return {
        "lease_version": 1,
        "slot_id": slot_id,
        "slot_path": str(slot_path(ctx, slot_id)),
        "branch": None,
        "agent": None,
        "issue_id": None,
        "task_label": None,
        "mode": None,
        "state": "free",
        "claimed_at": None,
        "last_opened_at": None,
        "last_checked_at": None,
        "stale_reason": None,
    }


def load_lease(ctx: RepoContext, slot_id: str) -> dict[str, Any]:
    path = lease_path(ctx, slot_id)
    if not path.exists():
        lease = blank_lease(ctx, slot_id)
        if slot_id in stable_slot_ids():
            save_lease(ctx, lease)
        return lease
    return json.loads(path.read_text(encoding="utf-8"))


def save_lease(ctx: RepoContext, lease: dict[str, Any]) -> None:
    path = lease_path(ctx, lease["slot_id"])
    path.write_text(json.dumps(lease, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def known_slot_ids(ctx: RepoContext, max_slots: int) -> list[str]:
    ids = set(stable_slot_ids())
    if ctx.state_dir.exists():
        for path in ctx.state_dir.glob("*.json"):
            slot_id = path.stem
            if SLOT_RE.match(slot_id):
                ids.add(slot_id)
    return sorted(ids, key=slot_sort_key)


def slot_sort_key(slot_id: str) -> tuple[int, int]:
    prefix, number = slot_id.split("-", 1)
    order = 0 if prefix == "slot" else 1
    return (order, int(number))


def sanitize_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug:
        raise SystemExit("Task label must contain at least one alphanumeric character.")
    return slug


def parse_branch(branch: str) -> dict[str, str]:
    match = BRANCH_RE.match(branch)
    if not match:
        raise SystemExit(
            "Branch must match <agent>/<type>/<issue>-<slug> "
            "(for example: codex/fix/7-safe-calculator)."
        )
    return match.groupdict()


def local_branch_exists(ctx: RepoContext, branch: str) -> bool:
    return run("git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", cwd=ctx.shared_root, check=False).returncode == 0


def remote_branch_exists(ctx: RepoContext, branch: str) -> bool:
    return run(
        "git",
        "show-ref",
        "--verify",
        "--quiet",
        f"refs/remotes/origin/{branch}",
        cwd=ctx.shared_root,
        check=False,
    ).returncode == 0


def origin_main_exists(ctx: RepoContext) -> bool:
    return run(
        "git",
        "show-ref",
        "--verify",
        "--quiet",
        "refs/remotes/origin/main",
        cwd=ctx.shared_root,
        check=False,
    ).returncode == 0


def main_exists(ctx: RepoContext) -> bool:
    return run(
        "git",
        "show-ref",
        "--verify",
        "--quiet",
        "refs/heads/main",
        cwd=ctx.shared_root,
        check=False,
    ).returncode == 0


def maybe_fetch_origin_main(ctx: RepoContext) -> None:
    if run("git", "remote", "get-url", "origin", cwd=ctx.shared_root, check=False).returncode != 0:
        return
    result = run("git", "fetch", "origin", "main", cwd=ctx.shared_root, check=False, capture_stderr=True)
    if result.returncode != 0 and not origin_main_exists(ctx):
        raise SystemExit(f"Failed to fetch origin/main:\n{result.stdout.strip()}")


@lru_cache(maxsize=8)
def cached_base_ref(shared_root: str) -> str:
    ctx = RepoContext(
        cwd_root=Path(shared_root),
        shared_root=Path(shared_root),
        common_dir=Path(shared_root) / ".git",
        worktrees_dir=Path(shared_root) / ".worktrees",
        state_dir=Path(shared_root) / ".worktrees" / "state",
    )
    maybe_fetch_origin_main(ctx)
    if origin_main_exists(ctx):
        return "origin/main"
    if main_exists(ctx):
        return "main"
    raise SystemExit("Could not find origin/main or local main to base a new worktree on.")


def base_ref(ctx: RepoContext) -> str:
    return cached_base_ref(str(ctx.shared_root))


def parse_worktree_list(ctx: RepoContext) -> list[dict[str, str]]:
    output = git("worktree", "list", "--porcelain", cwd=ctx.shared_root)
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in output.splitlines():
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, value = line.split(" ", 1)
        current[key] = value
    if current:
        entries.append(current)
    return entries


def branch_worktree_map(ctx: RepoContext) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entry in parse_worktree_list(ctx):
        branch_ref = entry.get("branch")
        path = entry.get("worktree")
        if branch_ref and path and branch_ref.startswith("refs/heads/"):
            mapping[branch_ref.removeprefix("refs/heads/")] = path
    return mapping


def path_worktree_map(ctx: RepoContext) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for entry in parse_worktree_list(ctx):
        branch_ref = entry.get("branch")
        path = entry.get("worktree")
        if branch_ref and path and branch_ref.startswith("refs/heads/"):
            mapping[path] = branch_ref.removeprefix("refs/heads/")
    return mapping


def git_status_dirty(path: Path) -> bool:
    return bool(git("-C", str(path), "status", "--porcelain"))


def branch_merged_into_main(ctx: RepoContext, branch: str) -> bool | None:
    if not local_branch_exists(ctx, branch):
        return None
    return run(
        "git",
        "merge-base",
        "--is-ancestor",
        branch,
        base_ref(ctx),
        cwd=ctx.shared_root,
        check=False,
    ).returncode == 0


def branch_last_commit(ctx: RepoContext, branch: str) -> str | None:
    if not local_branch_exists(ctx, branch):
        return None
    output = git("log", "-1", "--format=%cI", branch, cwd=ctx.shared_root)
    return output or None


def branch_open_pr_hint(ctx: RepoContext, branch: str) -> str | None:
    if not command_exists("gh"):
        return None
    result = run(
        "gh",
        "pr",
        "list",
        "--head",
        branch,
        "--state",
        "all",
        "--json",
        "number,state,url",
        cwd=ctx.shared_root,
        check=False,
        capture_stderr=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        items = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not items:
        return None
    item = items[0]
    return f"PR #{item['number']} {item['state'].lower()} ({item['url']})"


def observe_slot(ctx: RepoContext, lease: dict[str, Any], stale_hours: int) -> dict[str, Any]:
    slot_id = lease["slot_id"]
    slot_dir = slot_path(ctx, slot_id)
    branch = lease.get("branch")
    branch_paths = branch_worktree_map(ctx)
    path_branches = path_worktree_map(ctx)
    dirty = None
    checked_out_branch = path_branches.get(str(slot_dir))
    if slot_dir.exists() and checked_out_branch:
        dirty = git_status_dirty(slot_dir)

    merged = branch_merged_into_main(ctx, branch) if branch else None
    last_commit = branch_last_commit(ctx, branch) if branch else None
    pr_hint = branch_open_pr_hint(ctx, branch) if branch else None
    reasons: list[str] = []
    claimed_at = parse_iso(lease.get("claimed_at"))
    last_opened_at = parse_iso(lease.get("last_opened_at"))
    last_activity = last_opened_at or claimed_at

    if branch and branch in branch_paths and branch_paths[branch] != str(slot_dir):
        reasons.append(f"branch is checked out elsewhere: {branch_paths[branch]}")
    if lease["state"] != "free" and not slot_dir.exists():
        reasons.append("slot path is missing")
    if lease["state"] != "free" and slot_dir.exists() and checked_out_branch != branch:
        reasons.append(
            f"slot path is attached to {checked_out_branch or 'unknown branch'} instead of {branch or 'no branch'}"
        )
    if lease["state"] == "reserved" and last_activity:
        threshold = datetime.now(timezone.utc) - timedelta(hours=stale_hours)
        if last_activity < threshold and dirty is False:
            age_hours = int((datetime.now(timezone.utc) - last_activity).total_seconds() // 3600)
            reasons.append(f"lease is older than {age_hours}h and worktree is clean")

    safe_to_reclaim = False
    if lease["state"] != "free":
        if dirty is False and merged is True:
            safe_to_reclaim = True
        elif not slot_dir.exists() and (merged is True or not local_branch_exists(ctx, branch or "")):
            safe_to_reclaim = True

    return {
        "slot_path_exists": slot_dir.exists(),
        "checked_out_branch": checked_out_branch,
        "dirty": dirty,
        "merged": merged,
        "last_commit_at": last_commit,
        "pr_hint": pr_hint,
        "stale_reasons": reasons,
        "safe_to_reclaim": safe_to_reclaim,
    }


def link_shared_credentials(ctx: RepoContext, target_path: Path) -> None:
    credential_candidates = [
        ".env",
        ".env.local",
        ".env.development.local",
        ".env.test.local",
        ".env.production.local",
        ".npmrc",
        ".pypirc",
        ".netrc",
        "backend/data/gmail/client_secret.json",
        "backend/data/gmail/token.pickle",
    ]
    for rel_path in credential_candidates:
        source = ctx.shared_root / rel_path
        dest = target_path / rel_path
        if source.is_file() and not dest.exists() and not dest.is_symlink():
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.symlink_to(source)


def create_or_attach_worktree(ctx: RepoContext, slot_id: str, branch: str) -> None:
    target = slot_path(ctx, slot_id)
    branch_paths = branch_worktree_map(ctx)
    existing_branch_path = branch_paths.get(branch)
    if existing_branch_path:
        if Path(existing_branch_path).resolve() == target.resolve():
            return
        raise SystemExit(f"Branch {branch} is already checked out at {existing_branch_path}.")

    if target.exists():
        raise SystemExit(
            f"Slot path {target} already exists but is not available. "
            "Inspect with scripts/agent-status.sh before reusing it."
        )

    if local_branch_exists(ctx, branch):
        run("git", "worktree", "add", str(target), branch, cwd=ctx.shared_root)
    elif remote_branch_exists(ctx, branch):
        run("git", "worktree", "add", str(target), "-b", branch, f"origin/{branch}", cwd=ctx.shared_root)
    else:
        run("git", "worktree", "add", str(target), "-b", branch, base_ref(ctx), cwd=ctx.shared_root)
    link_shared_credentials(ctx, target)


def choose_slot(ctx: RepoContext, requested_slot: str | None, max_slots: int) -> str:
    slots = all_slot_ids(max_slots)
    if requested_slot:
        if requested_slot not in slots:
            raise SystemExit(
                f"Unknown slot {requested_slot}. Supported slots range from {slots[0]} to {slots[-1]}."
            )
        lease = load_lease(ctx, requested_slot)
        if lease["state"] == "free":
            return requested_slot
        raise SystemExit(f"Slot {requested_slot} is {lease['state']} and cannot be claimed automatically.")

    for slot_id in stable_slot_ids():
        if load_lease(ctx, slot_id)["state"] == "free":
            return slot_id

    for slot_id in dynamic_slot_ids(max_slots):
        lease = load_lease(ctx, slot_id)
        if lease_path(ctx, slot_id).exists() and lease["state"] == "free":
            return slot_id

    for slot_id in dynamic_slot_ids(max_slots):
        if not lease_path(ctx, slot_id).exists():
            return slot_id

    raise SystemExit(build_capacity_error(ctx, max_slots))


def build_capacity_error(ctx: RepoContext, max_slots: int) -> str:
    lines = [
        f"No free managed worktree slots are available (stable={DEFAULT_STABLE_SLOTS}, max={max_slots}).",
        "Run scripts/agent-status.sh to inspect leases, then release or reclaim slots explicitly.",
    ]
    for slot_id in known_slot_ids(ctx, max_slots):
        lease = load_lease(ctx, slot_id)
        if lease["state"] == "free":
            continue
        obs = observe_slot(ctx, lease, DEFAULT_STALE_HOURS)
        note = ", ".join(obs["stale_reasons"]) if obs["stale_reasons"] else "reserved"
        lines.append(f"- {slot_id}: {lease['state']} {lease.get('branch') or '-'} [{note}]")
    return "\n".join(lines)


def format_shell(payload: dict[str, Any]) -> str:
    lines = []
    for key, value in payload.items():
        if value is None:
            rendered = "''"
        else:
            rendered = shlex.quote(str(value))
        lines.append(f"{key}={rendered}")
    return "\n".join(lines)


def print_payload(payload: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif output_format == "shell":
        print(format_shell(payload))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")


def cmd_claim(args: argparse.Namespace) -> int:
    ctx = repo_context()
    ensure_dirs(ctx)

    if args.agent not in ALLOWED_AGENTS:
        raise SystemExit(f"Agent must be one of: {', '.join(sorted(ALLOWED_AGENTS))}.")
    if args.mode not in ALLOWED_MODES:
        raise SystemExit(f"Mode must be one of: {', '.join(sorted(ALLOWED_MODES))}.")

    if bool(args.branch) == bool(args.issue):
        raise SystemExit("Provide either --branch to resume work, or --issue/--type/--label to create a new branch.")
    if args.issue and (not args.type or not args.label):
        raise SystemExit("New slot claims require --issue, --type, and --label.")

    with state_lock(ctx):
        for slot_id in stable_slot_ids():
            load_lease(ctx, slot_id)

        if args.branch:
            branch = args.branch
            branch_parts = parse_branch(branch)
            if branch_parts["agent"] != args.agent:
                raise SystemExit(f"Branch {branch} belongs to agent {branch_parts['agent']}, not {args.agent}.")
            issue_id = int(branch_parts["issue"])
            task_label = branch_parts["slug"]
        else:
            issue_id = args.issue
            task_label = args.label
            branch = f"{args.agent}/{args.type}/{args.issue}-{sanitize_slug(args.label)}"

        # Reuse an existing lease for this branch when possible.
        for slot_id in known_slot_ids(ctx, args.max_slots):
            lease = load_lease(ctx, slot_id)
            if lease.get("branch") == branch and lease["state"] != "free":
                create_or_attach_worktree(ctx, slot_id, branch)
                lease.update(
                    {
                        "agent": args.agent,
                        "branch": branch,
                        "issue_id": issue_id,
                        "task_label": task_label,
                        "mode": args.mode,
                        "state": lease["state"],
                        "last_opened_at": now_iso(),
                        "last_checked_at": now_iso(),
                    }
                )
                save_lease(ctx, lease)
                print_payload(
                    {
                        "slot_id": slot_id,
                        "slot_path": str(slot_path(ctx, slot_id)),
                        "branch": branch,
                        "state": lease["state"],
                        "reused_existing_slot": True,
                    },
                    args.format,
                )
                return 0

        slot_id = choose_slot(ctx, args.slot, args.max_slots)
        create_or_attach_worktree(ctx, slot_id, branch)
        lease = blank_lease(ctx, slot_id)
        timestamp = now_iso()
        lease.update(
            {
                "branch": branch,
                "agent": args.agent,
                "issue_id": issue_id,
                "task_label": task_label,
                "mode": args.mode,
                "state": "reserved",
                "claimed_at": timestamp,
                "last_opened_at": timestamp,
                "last_checked_at": timestamp,
                "stale_reason": None,
            }
        )
        save_lease(ctx, lease)
        print_payload(
            {
                "slot_id": slot_id,
                "slot_path": str(slot_path(ctx, slot_id)),
                "branch": branch,
                "state": lease["state"],
                "reused_existing_slot": False,
            },
            args.format,
        )
    return 0


def mark_free(ctx: RepoContext, slot_id: str) -> None:
    lease = blank_lease(ctx, slot_id)
    lease["last_checked_at"] = now_iso()
    save_lease(ctx, lease)


def cmd_release(args: argparse.Namespace) -> int:
    ctx = repo_context()
    ensure_dirs(ctx)
    with state_lock(ctx):
        lease = load_lease(ctx, args.slot)
        if lease["state"] == "free":
            raise SystemExit(f"Slot {args.slot} is already free.")
        obs = observe_slot(ctx, lease, args.stale_hours)
        if obs["dirty"]:
            raise SystemExit(f"Refusing to release {args.slot}: worktree has uncommitted changes.")
        if obs["merged"] is False and not args.keep_branch:
            raise SystemExit(
                f"Refusing to release {args.slot}: branch {lease['branch']} is not merged into main. "
                "Re-run with --keep-branch to park the branch and free the slot."
            )
        slot_dir = slot_path(ctx, args.slot)
        if slot_dir.exists():
            run("git", "worktree", "remove", str(slot_dir), cwd=ctx.shared_root)
        mark_free(ctx, args.slot)
        print(f"Released {args.slot}.")
        if lease.get("branch") and args.keep_branch:
            print(f"Branch kept for later reuse: {lease['branch']}")
    return 0


def cmd_reclaim(args: argparse.Namespace) -> int:
    ctx = repo_context()
    ensure_dirs(ctx)
    actions: list[dict[str, str]] = []
    with state_lock(ctx):
        for slot_id in known_slot_ids(ctx, args.max_slots):
            lease = load_lease(ctx, slot_id)
            if lease["state"] == "free":
                continue
            obs = observe_slot(ctx, lease, args.stale_hours)
            if obs["safe_to_reclaim"]:
                actions.append({"slot_id": slot_id, "action": "reclaim", "reason": "clean and merged or missing"})
                if not args.dry_run:
                    slot_dir = slot_path(ctx, slot_id)
                    if slot_dir.exists():
                        run("git", "worktree", "remove", str(slot_dir), cwd=ctx.shared_root)
                    mark_free(ctx, slot_id)
                continue

            if obs["stale_reasons"]:
                reason = "; ".join(obs["stale_reasons"])
                actions.append({"slot_id": slot_id, "action": "mark-stale", "reason": reason})
                if not args.dry_run:
                    lease["state"] = "stale"
                    lease["stale_reason"] = reason
                    lease["last_checked_at"] = now_iso()
                    save_lease(ctx, lease)

    if args.json:
        print(json.dumps(actions, indent=2))
    elif not actions:
        print("No stale slots required action.")
    else:
        prefix = "Would" if args.dry_run else "Did"
        for action in actions:
            print(f"{prefix} {action['action']} {action['slot_id']}: {action['reason']}")
    return 0


def unmanaged_worktrees(ctx: RepoContext, max_slots: int) -> list[dict[str, str]]:
    managed_paths = {str(slot_path(ctx, slot_id)) for slot_id in all_slot_ids(max_slots)}
    items: list[dict[str, str]] = []
    for entry in parse_worktree_list(ctx):
        worktree = entry.get("worktree")
        branch_ref = entry.get("branch")
        if not worktree:
            continue
        if not worktree.startswith(str(ctx.worktrees_dir)):
            continue
        if worktree in managed_paths:
            continue
        if worktree == str(ctx.cwd_root):
            continue
        items.append(
            {
                "path": worktree,
                "branch": branch_ref.removeprefix("refs/heads/") if branch_ref else "(detached)",
            }
        )
    return items


def status_rows(ctx: RepoContext, max_slots: int, stale_hours: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for slot_id in known_slot_ids(ctx, max_slots):
        lease = load_lease(ctx, slot_id)
        obs = observe_slot(ctx, lease, stale_hours)
        row = dict(lease)
        row.update(obs)
        rows.append(row)
    return rows


def print_status(rows: list[dict[str, Any]], unmanaged: list[dict[str, str]]) -> None:
    header = (
        f"{'slot':<8} {'state':<8} {'agent':<6} {'mode':<4} {'dirty':<5} "
        f"{'merged':<6} {'branch':<42} notes"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        notes: list[str] = []
        if row.get("stale_reason"):
            notes.append(row["stale_reason"])
        notes.extend(row.get("stale_reasons") or [])
        if row.get("pr_hint"):
            notes.append(row["pr_hint"])
        note_text = "; ".join(dict.fromkeys(notes)) or "-"
        dirty = "-" if row["dirty"] is None else ("yes" if row["dirty"] else "no")
        merged = "-" if row["merged"] is None else ("yes" if row["merged"] else "no")
        print(
            f"{row['slot_id']:<8} {row['state']:<8} {(row.get('agent') or '-'): <6} "
            f"{(row.get('mode') or '-'): <4} {dirty:<5} {merged:<6} "
            f"{(row.get('branch') or '-'): <42} {note_text}"
        )
    if unmanaged:
        print("\nUnmanaged legacy worktrees")
        print("-------------------------")
        for item in unmanaged:
            print(f"- {item['path']} [{item['branch']}]")


def cmd_status(args: argparse.Namespace) -> int:
    ctx = repo_context()
    ensure_dirs(ctx)
    rows = status_rows(ctx, args.max_slots, args.stale_hours)
    unmanaged = unmanaged_worktrees(ctx, args.max_slots)
    if args.json:
        print(json.dumps({"slots": rows, "unmanaged_worktrees": unmanaged}, indent=2, sort_keys=True))
    else:
        print_status(rows, unmanaged)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage shared worktree slots for local coding agents.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    claim = subparsers.add_parser("claim", help="Claim or create a managed worktree slot.")
    claim.add_argument("--agent", required=True, choices=sorted(ALLOWED_AGENTS))
    claim.add_argument("--mode", default="cli", choices=sorted(ALLOWED_MODES))
    claim.add_argument("--issue", type=int)
    claim.add_argument("--type")
    claim.add_argument("--label")
    claim.add_argument("--branch")
    claim.add_argument("--slot")
    claim.add_argument("--max-slots", type=int, default=DEFAULT_MAX_SLOTS)
    claim.add_argument("--format", choices=["text", "json", "shell"], default="text")
    claim.set_defaults(func=cmd_claim)

    release = subparsers.add_parser("release", help="Release a slot when it is clearly safe to do so.")
    release.add_argument("--slot", required=True)
    release.add_argument("--keep-branch", action="store_true")
    release.add_argument("--stale-hours", type=int, default=DEFAULT_STALE_HOURS)
    release.set_defaults(func=cmd_release)

    reclaim = subparsers.add_parser("reclaim-stale", help="Mark stale slots and reclaim only when clearly safe.")
    reclaim.add_argument("--dry-run", action="store_true")
    reclaim.add_argument("--json", action="store_true")
    reclaim.add_argument("--max-slots", type=int, default=DEFAULT_MAX_SLOTS)
    reclaim.add_argument("--stale-hours", type=int, default=DEFAULT_STALE_HOURS)
    reclaim.set_defaults(func=cmd_reclaim)

    status = subparsers.add_parser("status", help="Show managed slot status and advisory cleanup hints.")
    status.add_argument("--json", action="store_true")
    status.add_argument("--max-slots", type=int, default=DEFAULT_MAX_SLOTS)
    status.add_argument("--stale-hours", type=int, default=DEFAULT_STALE_HOURS)
    status.set_defaults(func=cmd_status)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
