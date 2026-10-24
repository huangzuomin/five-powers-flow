"""CLI for bounded single-slice unattended execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import sys

from .adapters import CodexExec, OpenAIResponsesRoles, git
from .ledger import Ledger
from .runtime import SliceRuntime


def main() -> int:
    p = argparse.ArgumentParser(description="FPF unattended single-slice runtime v0.1")
    p.add_argument("--task-id", required=True)
    p.add_argument("--goal", required=True)
    p.add_argument("--dev-repo", required=True, type=Path)
    p.add_argument("--qa-worktree", required=True, type=Path)
    p.add_argument("--state-db", type=Path, default=Path(".fpf-runtime/slices.sqlite3"))
    p.add_argument("--model", required=True, help="Responses API model for DEV and QA role sessions")
    p.add_argument("--dev-check", required=True, help="Quoted argv, no shell")
    p.add_argument("--qa-check", required=True, help="Quoted argv, no shell")
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--max-steps", type=int, default=30)
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--status-only", action="store_true")
    args = p.parse_args()
    ledger = Ledger(args.state_db.resolve())
    if args.status_only:
        data = ledger.read(args.task_id)
        print(json.dumps({"state": data, "events": ledger.events(args.task_id)},
                         indent=2, ensure_ascii=False))
        return 0 if data else 2
    try:
        dev = args.dev_repo.resolve()
        base = git(dev, "rev-parse", "HEAD")
        state = ledger.read(args.task_id)
        if not state:
            ledger.create(args.task_id, args.goal, base, args.max_attempts)
        elif state["goal"] != args.goal:
            raise ValueError("Cannot change an existing slice goal")
        runtime = SliceRuntime(
            ledger, OpenAIResponsesRoles(args.model), CodexExec(),
            dev, args.qa_worktree,
            shlex.split(args.dev_check), shlex.split(args.qa_check),
            timeout=args.timeout)
        state = runtime.run(args.task_id, args.max_steps)
        print(json.dumps({"state": state["phase"], "attempts": state["attempt"],
                          "tested_sha": state["head_sha"], "report": state["report"],
                          "events": ledger.events(args.task_id)},
                         indent=2, ensure_ascii=False))
        return 0 if state["phase"] == "READY_FOR_OWNER_REVIEW" else 2
    except Exception as exc:
        print("[FPF RUNTIME ERROR] " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
