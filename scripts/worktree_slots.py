#!/usr/bin/env python3
"""Manage shared worktree slots for CLI-based coding agents."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shlex
import shutil
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
ALLOWED_AGENTS = {"codex", "claude", "opencode"}
ALLOWED_MODES = {"cli"}
BRANCH_RE = re.compile(
    r"^(?P<agent>codex|claude|opencode)/(?P<type>[a-z0-9][a-z0-9-]*)/(?P<issue>[0-9]+)-(?P<slug>[a-z0-9][a-z0-9-]*)$"
)
SLOT_RE = re.compile(r"^(slot|dyn)-[0-9]{2}$")
TYPE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
COMMAND_RE = re.compile(r"^[A-Za-z0-9._+-]+$")


@dataclass
class RepoContext:
    cwd_root: Path
    shared_root: Path
    common_dir: Path
    worktrees_dir: Path
    state_dir: Path


@dataclass(frozen=True)
class PullRequestInfo:
    number: int
    state: str
    url: str
    head_ref_oid: str | None


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
    if not name or not COMMAND_RE.fullmatch(name):
        return False
    return shutil.which(name) is not None


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


def known_max_slots(ctx: RepoContext, configured_max: int) -> int:
    highest = DEFAULT_STABLE_SLOTS
    for slot_id in known_slot_ids(ctx, configured_max):
        _, suffix = slot_id.split("-", 1)
        highest = max(highest, int(suffix))
    return max(validate_max_slots(configured_max), highest)


def slot_sort_key(slot_id: str) -> tuple[int, int]:
    prefix, number = slot_id.split("-", 1)
    order = 0 if prefix == "slot" else 1
    return (order, int(number))


def sanitize_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug:
        raise SystemExit("Task label must contain at least one alphanumeric character.")
    return slug


def validate_type(value: str) -> str:
    if not TYPE_RE.match(value):
        raise SystemExit("Type must match: ^[a-z0-9][a-z0-9-]*$")
    return value


def validate_slot_id(slot_id: str, max_slots: int) -> str:
    if not SLOT_RE.match(slot_id):
        raise SystemExit(f"Invalid slot id: {slot_id}. Expected slot-XX or dyn-XX.")
    if slot_id not in all_slot_ids(max_slots):
        supported = all_slot_ids(max_slots)
        raise SystemExit(f"Unknown slot {slot_id}. Supported slots range from {supported[0]} to {supported[-1]}.")
    return slot_id


def validate_max_slots(max_slots: int) -> int:
    if max_slots < DEFAULT_STABLE_SLOTS:
        raise SystemExit(
            f"WORKTREE_SLOT_MAX / --max-slots must be at least {DEFAULT_STABLE_SLOTS} "
            f"to cover the stable slot set."
        )
    return max_slots


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
    return [dict(entry) for entry in _parse_worktree_list_cached(str(ctx.shared_root))]


@lru_cache(maxsize=None)
def _parse_worktree_list_cached(shared_root: str) -> tuple[dict[str, str], ...]:
    output = git("worktree", "list", "--porcelain", cwd=Path(shared_root))
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in output.splitlines():
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        parts = line.split(" ", 1)
        if len(parts) == 1:
            current[parts[0]] = "true"
        else:
            key, value = parts
            current[key] = value
    if current:
        entries.append(current)
    return tuple(entries)


def clear_worktree_list_cache(ctx: RepoContext) -> None:
    _parse_worktree_list_cached.cache_clear()


def _parse_pull_request_info(item: dict[str, Any]) -> PullRequestInfo | None:
    number = item.get("number")
    state = item.get("state")
    url = item.get("url")
    if not isinstance(number, int) or not isinstance(state, str) or not isinstance(url, str):
        return None
    head_ref_oid = item.get("headRefOid")
    if head_ref_oid is not None and not isinstance(head_ref_oid, str):
        return None
    return PullRequestInfo(number=number, state=state, url=url, head_ref_oid=head_ref_oid)


@lru_cache(maxsize=128)
def cached_branch_pr_info(shared_root: str, branch: str) -> PullRequestInfo | None:
    if not command_exists("gh"):
        return None

    shared_root_path = Path(shared_root)
    result = run(
        "gh",
        "pr",
        "view",
        branch,
        "--json",
        "number,state,url,headRefOid",
        cwd=shared_root_path,
        check=False,
        capture_stderr=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        try:
            item = json.loads(result.stdout)
        except json.JSONDecodeError:
            item = None
        if isinstance(item, dict):
            info = _parse_pull_request_info(item)
            if info is not None:
                return info

    result = run(
        "gh",
        "pr",
        "list",
        "--head",
        branch,
        "--state",
        "all",
        "--json",
        "number,state,url,headRefOid",
        cwd=shared_root_path,
        check=False,
        capture_stderr=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        items = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(items, list) or not items:
        return None
    if not isinstance(items[0], dict):
        return None
    return _parse_pull_request_info(items[0])


def branch_pr_info(ctx: RepoContext, branch: str) -> PullRequestInfo | None:
    return cached_branch_pr_info(str(ctx.shared_root), branch)


def branch_tip_oid(ctx: RepoContext, branch: str) -> str | None:
    if not local_branch_exists(ctx, branch):
        return None
    output = git("rev-parse", branch, cwd=ctx.shared_root)
    return output or None


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


def worktree_entry_for_path(ctx: RepoContext, path: Path) -> dict[str, str] | None:
    for entry in parse_worktree_list(ctx):
        if entry.get("worktree") == str(path):
            return entry
    return None


def base_ref_oid(ctx: RepoContext) -> str:
    return git("rev-parse", base_ref(ctx), cwd=ctx.shared_root)


def commit_reachable_from_base_ref(ctx: RepoContext, commit_oid: str | None) -> bool:
    if not commit_oid:
        return False
    if commit_oid == base_ref_oid(ctx):
        return True
    return (
        run(
            "git",
            "merge-base",
            "--is-ancestor",
            commit_oid,
            base_ref(ctx),
            cwd=ctx.shared_root,
            check=False,
        ).returncode
        == 0
    )


def is_parked_entry(ctx: RepoContext, entry: dict[str, str] | None) -> bool:
    if not entry or entry.get("detached") != "true":
        return False
    return commit_reachable_from_base_ref(ctx, entry.get("HEAD"))


def git_status_dirty(path: Path) -> bool:
    return bool(git("-C", str(path), "status", "--porcelain"))


def ensure_branch_checked_out(ctx: RepoContext, path: Path, branch: str) -> None:
    if local_branch_exists(ctx, branch):
        run("git", "-C", str(path), "checkout", branch)
    elif remote_branch_exists(ctx, branch):
        run("git", "-C", str(path), "checkout", "-b", branch, f"origin/{branch}")
    else:
        run("git", "-C", str(path), "checkout", "-b", branch, base_ref(ctx))
    clear_worktree_list_cache(ctx)


def park_slot_worktree(ctx: RepoContext, slot_id: str) -> None:
    target = slot_path(ctx, slot_id)
    if not target.exists():
        return

    entry = worktree_entry_for_path(ctx, target)
    if entry is None:
        raise SystemExit(
            f"Release failed for {slot_id}: {target} exists but is not attached to a known managed worktree. "
            "Run scripts/agent-status.sh and inspect the worktree before retrying."
        )

    try:
        dirty = git_status_dirty(target)
    except Exception as exc:
        raise SystemExit(
            f"Release failed for {slot_id}: could not determine whether the worktree is dirty ({exc}). "
            "Inspect the slot manually and discuss with the user before retrying."
        ) from exc

    if dirty:
        raise SystemExit(
            f"Release failed for {slot_id}: the worktree has uncommitted changes. "
            "Fix those files before releasing the slot. If they are not needed, stash or discard them. "
            "If they matter, commit them and open or update a PR. If you are unsure, discuss it with the user."
        )

    if is_parked_entry(ctx, entry):
        return

    run("git", "-C", str(target), "checkout", "--detach", base_ref(ctx))
    clear_worktree_list_cache(ctx)


def branch_merged_into_main(ctx: RepoContext, branch: str) -> bool | None:
    if not local_branch_exists(ctx, branch):
        return None
    merged = (
        run(
            "git",
            "merge-base",
            "--is-ancestor",
            branch,
            base_ref(ctx),
            cwd=ctx.shared_root,
            check=False,
        ).returncode
        == 0
    )
    if merged:
        return True
    pr_info = branch_pr_info(ctx, branch)
    branch_tip = branch_tip_oid(ctx, branch)
    if pr_info is not None and pr_info.state == "MERGED" and branch_tip is not None and pr_info.head_ref_oid == branch_tip:
        return True
    return False


def branch_last_commit(ctx: RepoContext, branch: str) -> str | None:
    if not local_branch_exists(ctx, branch):
        return None
    output = git("log", "-1", "--format=%cI", branch, cwd=ctx.shared_root)
    return output or None


def branch_open_pr_hint(ctx: RepoContext, branch: str) -> str | None:
    info = branch_pr_info(ctx, branch)
    if info is None:
        return None
    return f"PR #{info.number} {info.state.lower()} ({info.url})"


def observe_slot(ctx: RepoContext, lease: dict[str, Any], stale_hours: int) -> dict[str, Any]:
    slot_id = lease["slot_id"]
    slot_dir = slot_path(ctx, slot_id)
    branch = lease.get("branch")
    branch_paths = branch_worktree_map(ctx)
    entry = worktree_entry_for_path(ctx, slot_dir)
    dirty = None
    checked_out_branch = None
    head_oid = None
    is_detached = False
    if entry is not None:
        branch_ref = entry.get("branch")
        head_oid = entry.get("HEAD")
        is_detached = entry.get("detached") == "true"
        if branch_ref and branch_ref.startswith("refs/heads/"):
            checked_out_branch = branch_ref.removeprefix("refs/heads/")
    parked = is_parked_entry(ctx, entry)
    if slot_dir.exists():
        try:
            dirty = git_status_dirty(slot_dir)
        except Exception:
            # Unknown worktree status is treated as unsafe so release/reclaim
            # paths do not discard uncommitted changes.
            dirty = True

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
    if lease["state"] != "free" and slot_dir.exists() and checked_out_branch != branch and not parked:
        reasons.append(
            f"slot path is attached to {checked_out_branch or ('detached at ' + head_oid[:12] if head_oid else 'unknown branch')} "
            f"instead of {branch or 'no branch'}"
        )
    if lease["state"] == "free" and slot_dir.exists():
        if not parked:
            reasons.append(
                f"free slot is not parked at {base_ref(ctx)} "
                f"(current state: {checked_out_branch or ('detached at ' + head_oid[:12] if head_oid else 'unknown')})"
            )
        elif dirty:
            reasons.append(f"free slot is parked at {base_ref(ctx)} with uncommitted changes")
    if lease["state"] == "reserved" and last_activity:
        threshold = datetime.now(timezone.utc) - timedelta(hours=stale_hours)
        if last_activity < threshold and dirty is False:
            age_hours = int((datetime.now(timezone.utc) - last_activity).total_seconds() // 3600)
            reasons.append(f"lease is older than {age_hours}h and worktree is clean")

    safe_to_reclaim = False
    if lease["state"] != "free":
        if dirty is False and parked:
            safe_to_reclaim = True
        elif dirty is False and merged is True:
            safe_to_reclaim = True
        elif not slot_dir.exists() and (merged is True or not local_branch_exists(ctx, branch or "")):
            safe_to_reclaim = True

    return {
        "slot_path_exists": slot_dir.exists(),
        "checked_out_branch": checked_out_branch,
        "head_oid": head_oid,
        "is_detached": is_detached,
        "is_parked": parked,
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
        entry = worktree_entry_for_path(ctx, target)
        checked_out_branch = None
        head_oid = None
        if entry is None:
            raise SystemExit(
                f"Slot path {target} already exists but is not attached to a known managed worktree. "
                "Inspect with scripts/agent-status.sh before reusing it."
            )
        branch_ref = entry.get("branch")
        if branch_ref and branch_ref.startswith("refs/heads/"):
            checked_out_branch = branch_ref.removeprefix("refs/heads/")
        head_oid = entry.get("HEAD")
        try:
            dirty = git_status_dirty(target)
        except Exception as exc:
            raise SystemExit(
                f"Could not determine whether {target} is clean ({exc}). "
                "Inspect the slot and discuss with the user before reusing it."
            ) from exc
        if dirty:
            raise SystemExit(
                f"Slot path {target} is not empty because it has uncommitted changes on "
                f"{checked_out_branch or ('detached at ' + head_oid[:12] if head_oid else 'an unknown revision')}. "
                "Release or clean that slot first."
            )
        if not is_parked_entry(ctx, entry):
            raise SystemExit(
                f"Slot path {target} is not empty because it is currently on "
                f"{checked_out_branch or ('detached at ' + head_oid[:12] if head_oid else 'an unknown revision')}. "
                f"Run scripts/release-slot.sh --slot {slot_id} first so the slot is parked at {base_ref(ctx)}."
            )
        ensure_branch_checked_out(ctx, target, branch)
        link_shared_credentials(ctx, target)
        return

    if local_branch_exists(ctx, branch):
        run("git", "worktree", "add", str(target), branch, cwd=ctx.shared_root)
    elif remote_branch_exists(ctx, branch):
        run("git", "worktree", "add", str(target), "-b", branch, f"origin/{branch}", cwd=ctx.shared_root)
    else:
        run("git", "worktree", "add", str(target), "-b", branch, base_ref(ctx), cwd=ctx.shared_root)
    clear_worktree_list_cache(ctx)
    link_shared_credentials(ctx, target)


def choose_slot(ctx: RepoContext, requested_slot: str | None, max_slots: int) -> str:
    max_slots = validate_max_slots(max_slots)
    slots = all_slot_ids(max_slots)
    if requested_slot:
        requested_slot = validate_slot_id(requested_slot, max_slots)
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
    max_slots = validate_max_slots(max_slots)
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
    max_slots = validate_max_slots(args.max_slots)

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
            branch = f"{args.agent}/{validate_type(args.type)}/{args.issue}-{sanitize_slug(args.label)}"

        # Reuse an existing lease for this branch when possible.
        for slot_id in known_slot_ids(ctx, max_slots):
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
                        "state": "reserved",
                        "claimed_at": lease.get("claimed_at") or now_iso(),
                        "last_opened_at": now_iso(),
                        "last_checked_at": now_iso(),
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
                        "reused_existing_slot": True,
                    },
                    args.format,
                )
                return 0

        slot_id = choose_slot(ctx, args.slot, max_slots)
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


def release_attention_items(rows: list[dict[str, Any]]) -> list[str]:
    items: list[str] = []
    for row in rows:
        slot_id = row["slot_id"]
        checked_out_branch = row.get("checked_out_branch")
        parked_label = "parked at main base commit"
        branch = row.get("branch") or checked_out_branch or "-"
        if row.get("dirty") is True and row.get("is_parked") is True:
            items.append(
                f"- {slot_id}: worktree is {parked_label} but has uncommitted files. "
                "Discuss this with the user before stashing, discarding, or committing them."
            )
        elif row.get("dirty") is True and not row.get("is_parked"):
            items.append(
                f"- {slot_id}: branch {branch} has uncommitted files. "
                "Discuss this with the user before stashing, committing, or opening/updating a PR."
            )
        elif row.get("state") != "free" and row.get("merged") is True:
            items.append(
                f"- {slot_id}: branch {row.get('branch') or branch} appears merged, but the slot is still reserved. "
                "Discuss with the user whether it should be released now."
            )
    return items


def print_release_status_summary(ctx: RepoContext, stale_hours: int, stream: Any = sys.stdout) -> None:
    max_slots = known_max_slots(ctx, DEFAULT_MAX_SLOTS)
    rows = status_rows(ctx, max_slots, stale_hours)
    unmanaged = unmanaged_worktrees(ctx, max_slots)
    print("Current managed slot status:", file=stream)
    print_status(rows, unmanaged, stream=stream)
    attention_items = release_attention_items(rows)
    if attention_items:
        print("\nSlots needing user attention:", file=stream)
        for item in attention_items:
            print(item, file=stream)
    else:
        print("\nNo managed slots currently need follow-up.", file=stream)


def cmd_release(args: argparse.Namespace) -> int:
    ctx = repo_context()
    ensure_dirs(ctx)
    slot_id = validate_slot_id(args.slot, known_max_slots(ctx, DEFAULT_MAX_SLOTS))
    with state_lock(ctx):
        lease = load_lease(ctx, slot_id)
        if lease["state"] == "free":
            print(f"Release failed for {slot_id}: the slot is already free.", file=sys.stderr)
            print("", file=sys.stderr)
            print_release_status_summary(ctx, args.stale_hours, stream=sys.stderr)
            return 1
        obs = observe_slot(ctx, lease, args.stale_hours)
        if obs["slot_path_exists"] and obs["dirty"] is not False:
            print(
                f"Release failed for {slot_id}: the worktree has uncommitted or unknown changes. "
                "Fix those files first. If they are not needed, stash or discard them. If they matter, "
                "commit them and open or update a PR. If you are unsure, discuss it with the user.",
                file=sys.stderr,
            )
            print("", file=sys.stderr)
            print_release_status_summary(ctx, args.stale_hours, stream=sys.stderr)
            return 1
        if (
            obs["slot_path_exists"]
            and not obs["is_parked"]
            and obs.get("checked_out_branch") != lease.get("branch")
        ):
            current_state = obs.get("checked_out_branch")
            if current_state is None:
                head_oid = obs.get("head_oid")
                current_state = f"detached at {head_oid[:12]}" if head_oid else "an unknown revision"
            print(
                f"Release failed for {slot_id}: the slot worktree is on {current_state}, not {lease['branch']}. "
                "Inspect the slot with scripts/agent-status.sh and discuss the next step with the user before retrying.",
                file=sys.stderr,
            )
            print("", file=sys.stderr)
            print_release_status_summary(ctx, args.stale_hours, stream=sys.stderr)
            return 1
        if obs["merged"] is False and not args.keep_branch and not obs["is_parked"]:
            print(
                f"Release failed for {slot_id}: branch {lease['branch']} is not merged into main. "
                f"Finish or merge that work first, or rerun with --keep-branch to park the branch at {base_ref(ctx)} "
                "and free the slot.",
                file=sys.stderr,
            )
            print("", file=sys.stderr)
            print_release_status_summary(ctx, args.stale_hours, stream=sys.stderr)
            return 1
        try:
            park_slot_worktree(ctx, slot_id)
        except SystemExit as exc:
            print(str(exc), file=sys.stderr)
            print("", file=sys.stderr)
            print_release_status_summary(ctx, args.stale_hours, stream=sys.stderr)
            return 1
        mark_free(ctx, slot_id)
        print(f"Released {slot_id}.")
        if lease.get("branch") and args.keep_branch:
            print(f"Branch kept for later reuse: {lease['branch']}")
        print("")
        print_release_status_summary(ctx, args.stale_hours)
    return 0


def cmd_reclaim(args: argparse.Namespace) -> int:
    ctx = repo_context()
    ensure_dirs(ctx)
    max_slots = known_max_slots(ctx, args.max_slots)
    actions: list[dict[str, str]] = []
    with state_lock(ctx):
        for slot_id in known_slot_ids(ctx, max_slots):
            lease = load_lease(ctx, slot_id)
            if lease["state"] == "free":
                continue
            obs = observe_slot(ctx, lease, args.stale_hours)
            if obs["safe_to_reclaim"]:
                reason = f"clean slot already parked at {base_ref(ctx)}" if obs["is_parked"] else "clean and merged or missing"
                action = {"slot_id": slot_id, "action": "reclaim", "reason": reason}
                actions.append(action)
                if not args.dry_run:
                    try:
                        if obs["slot_path_exists"]:
                            park_slot_worktree(ctx, slot_id)
                        mark_free(ctx, slot_id)
                    except SystemExit as exc:
                        action["action"] = "mark-stale"
                        action["reason"] = f"reclaim blocked: {exc}"
                        lease["state"] = "stale"
                        lease["stale_reason"] = str(exc)
                        lease["last_checked_at"] = now_iso()
                        save_lease(ctx, lease)
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
    managed_paths = {str(slot_path(ctx, slot_id)) for slot_id in all_slot_ids(validate_max_slots(max_slots))}
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
    max_slots = validate_max_slots(max_slots)
    rows: list[dict[str, Any]] = []
    for slot_id in known_slot_ids(ctx, max_slots):
        lease = load_lease(ctx, slot_id)
        obs = observe_slot(ctx, lease, stale_hours)
        row = dict(lease)
        row.update(obs)
        rows.append(row)
    return rows


def print_status(rows: list[dict[str, Any]], unmanaged: list[dict[str, str]], stream: Any = sys.stdout) -> None:
    header = (
        f"{'slot':<8} {'state':<8} {'agent':<8} {'mode':<4} {'dirty':<5} "
        f"{'merged':<6} {'branch':<42} notes"
    )
    print(header, file=stream)
    print("-" * len(header), file=stream)
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
            f"{row['slot_id']:<8} {row['state']:<8} {(row.get('agent') or '-'): <8} "
            f"{(row.get('mode') or '-'): <4} {dirty:<5} {merged:<6} "
            f"{(row.get('branch') or '-'): <42} {note_text}",
            file=stream,
        )
    if unmanaged:
        print("\nUnmanaged worktrees", file=stream)
        print("-------------------", file=stream)
        for item in unmanaged:
            print(f"- {item['path']} [{item['branch']}]", file=stream)


def cmd_status(args: argparse.Namespace) -> int:
    ctx = repo_context()
    ensure_dirs(ctx)
    max_slots = known_max_slots(ctx, args.max_slots)
    rows = status_rows(ctx, max_slots, args.stale_hours)
    unmanaged = unmanaged_worktrees(ctx, max_slots)
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
    reclaim.add_argument("--all", action="store_true", help="Explicitly sweep every managed slot (same safety rules).")
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
