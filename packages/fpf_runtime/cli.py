"""Command-line entrypoint for API-agent + Codex + optional GitHub PR integration + Daemon."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import signal
import sys

from .adapters import CodexExec, OpenAIResponsesRoles, git
from .ledger import Ledger
from .runtime import SliceRuntime


def handle_daemon_command(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="fpf daemon", description="FPF Coordinator background daemon control")
    parser.add_argument("action", choices=["start", "stop", "status", "tick"], help="Daemon control action")
    parser.add_argument("--state-db", type=Path, default=Path(".fpf-runtime/coordinator.sqlite3"))
    parser.add_argument("--pid-file", type=Path, default=Path(".fpf-runtime/daemon.pid"))
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--background", action="store_true", default=False)
    args = parser.parse_args(argv)

    from packages.fpf_runtime.daemon import DaemonConfig, DaemonServer, is_pid_alive

    cfg = DaemonConfig(
        state_db_path=args.state_db,
        pid_file=args.pid_file,
        interval_seconds=args.interval,
    )
    server = DaemonServer(cfg)

    if args.action == "start":
        print(f"Starting FPF coordinator daemon (ID: {cfg.daemon_id})...")
        server.start(background=args.background)
        print("Daemon running.")
        return 0
    elif args.action == "stop":
        if cfg.pid_file.exists():
            try:
                pid = int(cfg.pid_file.read_text(encoding="utf-8").strip())
                if is_pid_alive(pid):
                    if sys.platform == "win32":
                        import ctypes
                        PROCESS_TERMINATE = 0x0001
                        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, 0, pid)
                        if handle:
                            ctypes.windll.kernel32.TerminateProcess(handle, 0)
                            ctypes.windll.kernel32.CloseHandle(handle)
                    else:
                        os.kill(pid, signal.SIGTERM)
                cfg.pid_file.unlink(missing_ok=True)
                print(f"Daemon process {pid} stopped.")
                return 0
            except Exception as e:
                print(f"Failed to stop daemon: {e}", file=sys.stderr)
                return 1
        print("Daemon PID file not found, daemon appears stopped.")
        return 0
    elif args.action == "status":
        st = server.status()
        print(json.dumps(st, indent=2, ensure_ascii=False))
        return 0
    elif args.action == "tick":
        res = server.tick_once()
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "daemon":
        return handle_daemon_command(sys.argv[2:])

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
