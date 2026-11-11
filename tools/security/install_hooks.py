"""Install the repository hooks that gate secret material (G3).

Sets ``core.hooksPath`` to ``.githooks`` so a fresh clone gets the same
pre-commit gate as the maintainers. Existing hooks under ``.git/hooks`` are
*reported*, never moved or deleted: silently shadowing a maintainer's hook
would be a regression, so this tool refuses to hide one without saying so.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def legacy_hooks(root: Path) -> list[str]:
    hooks_dir = root / ".git" / "hooks"
    if not hooks_dir.is_dir():
        return []
    return sorted(
        p.name
        for p in hooks_dir.iterdir()
        if p.is_file() and not p.name.endswith(".sample")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install FPF git hooks")
    parser.add_argument("--check", action="store_true", help="report, do not modify")
    args = parser.parse_args(argv)

    root = Path(_git("rev-parse", "--show-toplevel"))
    target = ".githooks"
    if not (root / target / "pre-commit").is_file():
        print(f"missing {target}/pre-commit; run from a full checkout", file=sys.stderr)
        return 1

    current = ""
    result = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"], capture_output=True, text=True
    )
    if result.returncode == 0:
        current = result.stdout.strip()

    shadowed = [name for name in legacy_hooks(root) if name != "pre-commit"]
    if shadowed:
        print(
            "WARNING: these .git/hooks entries will stop running once "
            f"core.hooksPath={target} takes effect: {', '.join(shadowed)}",
            file=sys.stderr,
        )
        print(
            "Port anything still needed into .githooks/ before relying on it.",
            file=sys.stderr,
        )

    if current == target:
        print(f"already installed (core.hooksPath={target})")
        return 0
    if args.check:
        print(f"core.hooksPath is {current or '(unset)'}; would set {target}")
        return 0

    _git("config", "core.hooksPath", target)
    print(f"installed: core.hooksPath={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
