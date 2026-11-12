# -*- coding: utf-8 -*-
"""CLI for G4 scheduled reconciliation and explicitly dispatched projection PRs."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Mapping

from .events import event_log_digest
from .github_source import (
    GitHubSourceError,
    build_events_from_pr,
    create_check_run,
    find_pr_for_task,
    latest_audit_status,
    main_tip,
)
from .reconcile import audit_is_fresh, reconcile_projection, write_report
from .reducer import Reduction, projection_tasks_digest, reduce_events


LEDGER_PATH = Path("packages/fpf_coordinator/dispatch/state-ledger.json")
GENERATOR = "fpf-state-projector/v1"


def _event_log_digest(events: Any) -> str:
    return event_log_digest(events)


def genesis_ledger(repo: str) -> dict[str, Any]:
    digest = event_log_digest(())
    return {
        "schema_version": "fpf.state-ledger/v1",
        "source": {
            "backend": "github",
            "repo": repo,
            "audit_check_run_id": None,
            "audit_run_id": None,
            "audit_completed_at": None,
            "as_of_event_id": None,
            "as_of_occurred_at": None,
            "event_ids": [],
            "event_count": 0,
            "pending_event_count": 0,
            "event_log_digest": digest,
            "projection_digest": projection_tasks_digest([]),
            "complete": True,
            "generated_by": GENERATOR,
        },
        "tasks": [],
    }


def ledger_from_reduction(
    reduction: Reduction,
    repo: str,
    audit: Mapping[str, Any] | None,
) -> dict[str, Any]:
    events = list(reduction.ordered_events)
    task = copy.deepcopy(dict(reduction.projection))
    task["aggregate_version"] = 1 + len(reduction.event_ids)
    source = {
        "backend": "github",
        "repo": repo,
        "audit_check_run_id": (audit or {}).get("latest_run_id"),
        "audit_run_id": (audit or {}).get("latest_run_id"),
        "audit_completed_at": (audit or {}).get("latest_completed_at"),
        "as_of_event_id": reduction.event_ids[-1] if reduction.event_ids else None,
        "as_of_occurred_at": events[-1].occurred_at if events else None,
        "event_ids": list(reduction.event_ids),
        "event_count": len(reduction.event_ids),
        "pending_event_count": 0,
        "event_log_digest": reduction.event_log_digest,
        "projection_digest": projection_tasks_digest([task]),
        "complete": True,
        "generated_by": GENERATOR,
    }
    return {
        "schema_version": "fpf.state-ledger/v1",
        "source": source,
        "tasks": [task],
    }


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"state ledger is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "fpf.state-ledger/v1":
        raise ValueError("state ledger schema_version is invalid")
    return value


def write_ledger(path: Path, ledger: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(ledger), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def ledger_has_content(path: Path) -> bool:
    """A ledger that already carries events must be refreshed by an audit first."""
    try:
        if not path.is_file():
            return False
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(value, dict):
        return False
    source = value.get("source")
    return bool(isinstance(source, Mapping) and source.get("event_ids"))


def _token(name: str) -> str:
    return os.environ.get(name, "")


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--token-env", default="GH_TOKEN")


def _reduce_from_github(args: argparse.Namespace) -> tuple[Reduction, str]:
    token = _token(args.token_env)
    pr_number = int(args.pr_number)
    if pr_number <= 0:
        pr_number = find_pr_for_task(args.repo, args.task_id, token)
    batch = build_events_from_pr(
        args.repo, pr_number, args.task_id, args.project_id, token,
    )
    reduction = reduce_events(
        batch, task_id=args.task_id, project_id=args.project_id, complete=batch.complete,
    )
    return reduction, token


def command_genesis(args: argparse.Namespace) -> int:
    ledger = genesis_ledger(args.repo)
    write_ledger(Path(args.out), ledger)
    print(json.dumps(ledger["source"], ensure_ascii=False, sort_keys=True))
    return 0


def command_project(args: argparse.Namespace) -> int:
    reduction, token = _reduce_from_github(args)
    audit = latest_audit_status(args.repo, token)
    if ledger_has_content(Path(args.out)):
        fresh, reason = audit_is_fresh(
            audit, max_age_seconds=args.max_audit_age_seconds,
        )
        if not fresh:
            raise ValueError(f"projection requires a fresh passing audit: {reason}")
    ledger = ledger_from_reduction(reduction, args.repo, audit)
    write_ledger(Path(args.out), ledger)
    if args.event_log:
        Path(args.event_log).write_text(
            "\n".join(
                json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True)
                for event in reduction.ordered_events
            ) + ("\n" if reduction.ordered_events else ""),
            encoding="utf-8",
        )
    print(json.dumps({
        "status": "GENERATED",
        "task_id": args.task_id,
        "event_count": len(reduction.event_ids),
        "event_log_digest": reduction.event_log_digest,
        "projection_digest": reduction.projection_digest,
        "ledger": str(args.out),
    }, ensure_ascii=False, sort_keys=True))
    return 0


def command_reconcile(args: argparse.Namespace) -> int:
    reduction, token = _reduce_from_github(args)
    ledger = load_ledger(Path(args.ledger))
    audit = latest_audit_status(args.repo, token)
    result = reconcile_projection(
        reduction,
        ledger,
        audit=audit,
        max_audit_age_seconds=args.max_audit_age_seconds,
        require_fresh_audit=False,
    )
    tip = main_tip(args.repo, token)
    summary = json.dumps({
        **result,
        "task_id": args.task_id,
        "as_of_event_id": reduction.event_ids[-1] if reduction.event_ids else None,
        "event_count": len(reduction.event_ids),
        "event_log_digest": reduction.event_log_digest,
        "audit_run_id": os.environ.get("GITHUB_RUN_ID"),
    }, ensure_ascii=False, sort_keys=True)
    if args.report:
        write_report(args.report, {
            **result,
            "task_id": args.task_id,
            "main_tip_sha": tip,
            "audit": dict(audit),
        })
    if not args.no_check_run:
        try:
            check = create_check_run(
                args.repo,
                token,
                head_sha=tip,
                conclusion="success" if result["status"] == "PASS" else "failure",
                summary=summary,
                check_name=args.check_name,
            )
            print(json.dumps({"audit_check_run_id": check.get("id")}, ensure_ascii=False))
        except GitHubSourceError as exc:
            print("audit check-run failed: " + str(exc), file=sys.stderr)
            return 2
    print(summary)
    return 0 if result["status"] == "PASS" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="FPF G4 state ledger projector")
    sub = parser.add_subparsers(dest="command", required=True)

    genesis = sub.add_parser("genesis", help="emit the canonical empty ledger")
    genesis.add_argument("--repo", required=True)
    genesis.add_argument("--out", required=True)
    genesis.set_defaults(func=command_genesis)

    project = sub.add_parser("project", help="generate a ledger candidate from GitHub facts")
    _common(project)
    project.add_argument("--out", default=str(LEDGER_PATH))
    project.add_argument("--event-log")
    project.add_argument("--max-audit-age-seconds", type=int, default=1800)
    project.set_defaults(func=command_project)

    reconcile = sub.add_parser("reconcile", help="independently replay and compare the ledger")
    _common(reconcile)
    reconcile.add_argument("--ledger", default=str(LEDGER_PATH))
    reconcile.add_argument("--report")
    reconcile.add_argument("--max-audit-age-seconds", type=int, default=1800)
    reconcile.add_argument(
        "--check-name", default="fpf-state-ledger-audit",
        help="a pre-merge trial must use the -trial suffix, never the authoritative name",
    )
    reconcile.add_argument("--no-check-run", action="store_true")
    reconcile.set_defaults(func=command_reconcile)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (OSError, ValueError, GitHubSourceError, json.JSONDecodeError) as exc:
        print("G4 projector blocked: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
