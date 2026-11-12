# -*- coding: utf-8 -*-
"""H2 worktree lifecycle CLI.  Dry-run by default; ``repair`` is not here.

``repair`` is deliberately absent (Q7): a tool that both judges and repairs
can quietly turn "unprovable" into "fine".  Repair is a separate decision with
its own authorization, so the reclaim surface stays read/verify only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from packages.fpf_coordinator.worktree import (
    gitops,
    marker as marker_mod,
    policy as policy_mod,
    promotion,
    reclaim,
)

EXIT_OK = 0
EXIT_HOLD = 2
EXIT_POLICY = 3
EXIT_INVALID = 4


def _repo(value: str) -> Path:
    return Path(value).resolve()


def cmd_create(args) -> int:
    repo = _repo(args.repo)
    policy = policy_mod.load(repo)
    root = Path(args.root) if args.root else repo / policy.worktree_root
    target = root / args.name
    stations = repo / ".fpf" / "stations.yaml"
    owner = {"login": args.login, "station": args.station}
    try:
        marker = marker_mod.create(
            task_id=args.task_id, base_sha=args.base, owner=owner,
            branch=args.branch, detached_head_sha=args.detached,
            work_order_id=args.work_order, ttl_days=args.ttl_days,
            stations_path=stations)
    except marker_mod.MarkerError as exc:
        print(f"MARKER_INVALID: {exc}", file=sys.stderr)
        return EXIT_INVALID
    if target.exists():
        print(f"TARGET_EXISTS: {target}", file=sys.stderr)
        return EXIT_INVALID
    if args.detached:
        argv = ["git", "-C", str(repo), "worktree", "add", "--detach",
                str(target), args.detached]
    else:
        short = (args.branch or "").replace("refs/heads/", "")
        argv = ["git", "-C", str(repo), "worktree", "add", "-b", short,
                str(target), args.base]
    result = gitops.run(argv)
    if result.exit != 0:
        print(f"WORKTREE_ADD_FAILED: {result.stderr.strip()}", file=sys.stderr)
        return EXIT_INVALID
    try:
        marker_mod.write(target, marker)
    except marker_mod.MarkerError as exc:
        gitops.run(["git", "-C", str(repo), "worktree", "remove", str(target)])
        print(f"MARKER_WRITE_FAILED (worktree rolled back): {exc}", file=sys.stderr)
        return EXIT_INVALID
    print(json.dumps({"created": str(target), "digest": marker["digest"]}))
    return EXIT_OK


def cmd_scan(args) -> int:
    repo = _repo(args.repo)
    policy = policy_mod.load(repo)
    ledger = None
    if args.ledger:
        ledger = promotion.load(args.ledger)
    verdicts = reclaim.scan(repo, policy=policy)
    rows = []
    for verdict in verdicts:
        row = verdict.to_dict()
        if ledger is not None and verdict.marker_state is not None:
            try:
                marker = marker_mod.read(verdict.path)
                row["promotion"] = promotion.evaluate(
                    marker, ledger, head_sha=verdict.head_sha).__dict__
            except (FileNotFoundError, marker_mod.MarkerError):
                row["promotion"] = None
        rows.append(row)
    plan = reclaim.build_plan(verdicts, policy)
    report = {"scan": rows, "plan": plan, "policy_sha256": policy.sha256()}
    if args.json:
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"candidates": len(plan["candidates"]),
                      "held": len(plan["held"]),
                      "plan_digest": plan["plan_digest"]}))
    violations = [row for row in rows if row["decision"] == "POLICY_VIOLATION"]
    return EXIT_POLICY if violations else (EXIT_OK if not plan["candidates"] else EXIT_OK)


def cmd_reclaim(args) -> int:
    repo = _repo(args.repo)
    policy = policy_mod.load(repo)
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    archive_root = Path(args.archive_root) if args.archive_root else \
        repo / policy.archive_root
    outcome = reclaim.reclaim_batch(
        plan, repo=repo, policy=policy, archive_root=archive_root,
        run_id=args.run_id, apply=args.apply, confirm=args.confirm,
        only=args.only, ack_stash=args.ack_stash)
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    if outcome["decision"] == "REFUSED":
        return EXIT_INVALID
    if outcome["decision"] == "STOPPED":
        return EXIT_HOLD
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="worktree_lifecycle")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--repo", default=".")
    create.add_argument("--name", required=True)
    create.add_argument("--task-id", required=True)
    create.add_argument("--branch")
    create.add_argument("--detached")
    create.add_argument("--base", required=True)
    create.add_argument("--work-order")
    create.add_argument("--login", default="huangzuomin")
    create.add_argument("--station", default="ST-DEV-AUTHOR-01")
    create.add_argument("--ttl-days", type=int, default=14)
    create.add_argument("--root")
    create.set_defaults(func=cmd_create)

    scan = sub.add_parser("scan")
    scan.add_argument("--repo", default=".")
    scan.add_argument("--json")
    scan.add_argument("--ledger")
    scan.add_argument("--sync-state", action="store_true")
    scan.set_defaults(func=cmd_scan)

    reclaim_cmd = sub.add_parser("reclaim")
    reclaim_cmd.add_argument("--repo", default=".")
    reclaim_cmd.add_argument("--plan", required=True)
    reclaim_cmd.add_argument("--apply", action="store_true")
    reclaim_cmd.add_argument("--confirm")
    reclaim_cmd.add_argument("--only")
    reclaim_cmd.add_argument("--ack-stash", action="store_true")
    reclaim_cmd.add_argument("--archive-root")
    reclaim_cmd.add_argument("--run-id", default="local")
    reclaim_cmd.set_defaults(func=cmd_reclaim)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
