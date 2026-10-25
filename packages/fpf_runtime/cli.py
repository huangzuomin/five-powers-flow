"""Command-line entrypoint for API-agent + Codex + optional GitHub PR integration."""
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
    p = argparse.ArgumentParser(description="FPF single-slice integrated runtime 0.2")
    p.add_argument("--task-id", required=True)
    p.add_argument("--goal")
    p.add_argument("--dev-repo", type=Path)
    p.add_argument("--qa-worktree", type=Path)
    p.add_argument("--state-db", type=Path, default=Path(".fpf-runtime/slices.sqlite3"))
    p.add_argument("--model", help="API model for role sessions")
    p.add_argument("--base-url", default=None, help="OpenAI Responses API base URL (default: OPENAI_BASE_URL or https://api.openai.com/v1)")
    p.add_argument("--role-backend", choices=["agents", "responses"], default="agents")
    p.add_argument("--dev-check", help="Quoted argv (not shell)")
    p.add_argument("--qa-check", help="Quoted argv (not shell)")
    p.add_argument("--max-attempts", type=int, default=3)
    p.add_argument("--max-steps", type=int, default=30)
    p.add_argument("--timeout", type=int, default=600)
    p.add_argument("--status-only", action="store_true")
    p.add_argument("--publish-pr", action="store_true",
                   help="EXPLICITLY enable feature branch push and draft GitHub PR creation")
    p.add_argument("--base-branch", default="main")
    p.add_argument("--qa-evidence-dir", type=Path,
                   help="Independent runner EVID files: DIR/TASK/SHA/EVID-XX.ext")
    p.add_argument("--qa-profile", default="Library")
    args = p.parse_args()

    ledger = Ledger(args.state_db.resolve())
    if args.status_only:
        state = ledger.read(args.task_id)
        print(json.dumps({"state": state, "events": ledger.events(args.task_id)},
                         indent=2, ensure_ascii=False))
        return 0 if state else 2
    if not all((args.goal, args.dev_repo, args.qa_worktree, args.model,
                args.dev_check, args.qa_check)):
        p.error("--goal, --dev-repo, --qa-worktree, --model, --dev-check and --qa-check required")
    try:
        dev = args.dev_repo.resolve()
        base = git(dev, "rev-parse", "HEAD")
        old = ledger.read(args.task_id)
        if old:
            if old["goal"] != args.goal:
                raise ValueError("Existing slice goal may not change")
        else:
            ledger.create(args.task_id, args.goal, base, args.max_attempts)
        if args.role_backend == "agents":
            from .sdk_roles import AgentsSDKRoles
            roles = AgentsSDKRoles(args.model, args.task_id,
                                   args.state_db.resolve().with_suffix(".sessions.sqlite3"))
        else:
            roles = OpenAIResponsesRoles(args.model, base_url=args.base_url)

        publisher = None
        if args.publish_pr:
            from .github_pr import GhDraftPublisher
            publisher = GhDraftPublisher(args.base_branch)
        runtime = SliceRuntime(
            ledger, roles, CodexExec(), dev, args.qa_worktree,
            shlex.split(args.dev_check, posix=sys.platform != "win32"),
            shlex.split(args.qa_check, posix=sys.platform != "win32"),
            timeout=args.timeout, publisher=publisher,
            evidence_root=args.state_db.resolve().parent / "evidence",
            qa_evidence_dir=args.qa_evidence_dir, qa_profile=args.qa_profile)
        state = runtime.run(args.task_id, max_steps=args.max_steps)
        print(json.dumps(
            {"state": state["phase"], "attempts": state["attempt"],
             "tested_sha": state["head_sha"], "draft_pr": state.get("pr_url"),
             "report": state["report"], "events": ledger.events(args.task_id)},
            indent=2, ensure_ascii=False))
        return 0 if state["phase"] == "READY_FOR_OWNER_REVIEW" else 2
    except Exception as exc:
        print("[FPF ERROR] " + type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
