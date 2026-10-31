"""One entrypoint for fpf init, fpf doctor and existing slice runtime."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .bootstrap import plan, apply, doctor


def main() -> int:
    p = argparse.ArgumentParser(prog="fpf", description="Five Powers Flow tooling")
    commands = p.add_subparsers(dest="command", required=True)
    ini = commands.add_parser("init", help="Plan or create project bootstrap worktrees")
    ini.add_argument("--repo", type=Path, required=True)
    ini.add_argument("--workspace-root", type=Path, required=True)
    ini.add_argument("--project-id", required=True)
    ini.add_argument("--title", default="")
    ini.add_argument("--agent-mode", choices=("api", "manual"), default="api")
    ini.add_argument("--docs-dir", default="docs")
    ini.add_argument("--base-ref", default="HEAD")
    ini.add_argument("--rollback", action="store_true",
                     help="Explicitly rollback a safely identified incomplete bootstrap")
    ini.add_argument("--allow-existing-governance", action="store_true",
                     help="Preserve existing governance files present in baseline")
    ini.add_argument("--apply", action="store_true",
                     help="Create bootstrap, DEV and QA worktrees; does not commit or push")
    doc = commands.add_parser("doctor", help="Check existing project bootstrap")
    doc.add_argument("--repo", type=Path, required=True)
    doc.add_argument("--workspace-root", type=Path, required=True)
    doc.add_argument("--project-id", required=True)
    doc.add_argument("--check", action="store_true",
                     help="Only test physical provisioning; does not claim PROJECT_READY")
    commands.add_parser("run", help="Existing single-slice runtime (see --help there)")
    args, rest = p.parse_known_args()
    if args.command != "run" and rest:
        p.error("Unexpected arguments: " + " ".join(rest))
    try:
        if args.command == "init":
            if args.rollback:
                from .bootstrap import rollback
                outcome = rollback(args.repo, args.workspace_root, args.project_id)
                print(json.dumps(outcome, ensure_ascii=False, indent=2))
                return 0
            proposal = plan(args.repo, args.workspace_root, args.project_id,
                            args.title, args.agent_mode, args.base_ref, args.docs_dir,
                            allow_existing_governance=args.allow_existing_governance)
            if args.apply:
                outcome = apply(args.repo, proposal)
                print(json.dumps(outcome, ensure_ascii=False, indent=2))
            else:
                summary = {k: v for k, v in proposal.items() if k != "files"}
                summary["generated_files"] = sorted(proposal["files"])
                print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0
        if args.command == "doctor":
            result = doctor(args.repo, args.workspace_root, args.project_id,
                            require_ready=not args.check)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["ok"] else 2
        # The subcommand delegates to the original CLI without changing its arguments.
        from packages.fpf_runtime.cli import main as runtime_main
        old_argv = sys.argv
        try:
            sys.argv = [old_argv[0], *rest]
            return runtime_main()
        finally:
            sys.argv = old_argv
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print("FPF bootstrap error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
