"""Deterministic secret scanner for the FPF repository (G3).

Scans a repository for commit-able secret material. Three modes:

  --staged          scan the blobs staged in the index (pre-commit gate)
  --tracked         scan every file tracked by git (default)
  --path <dir>      scan a directory tree (used by the test-suite)

Exit code is 0 only when no finding was produced. The scanner is deliberately
pattern-based and offline: it never contacts a network service and never reads
credential material outside the paths it was asked to scan.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path


MAX_BYTES = 2_000_000
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache"}

# Public placeholders published in vendor documentation. They are not secrets;
# keeping the list exact and tiny avoids turning a real credential into a
# "known example" by accident.
ALLOWED_EXACT = frozenset({"AKIAIOSFODNN7EXAMPLE"})

# A line carrying this marker is skipped. The marker must state a reason:
#   AWS_ACCESS_KEY_ID = "AKIA..."  # fpf-secret-scan: allow vendor sample
SUPPRESS_MARKER = "fpf-secret-scan: allow"


@dataclass(frozen=True)
class Rule:
    rule_id: str
    pattern: re.Pattern[str]
    note: str


RULES: tuple[Rule, ...] = (
    Rule(
        "PEM-PRIVATE-KEY",
        re.compile(r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----"),  # fpf-secret-scan: allow rule definition
        "PEM private key block",
    ),
    Rule(
        "AWS-ACCESS-KEY",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "AWS access key id",
    ),
    Rule(
        "GITHUB-TOKEN",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
        "GitHub personal/installation token",
    ),
    Rule(
        "GITHUB-FINE-GRAINED-PAT",
        re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
        "GitHub fine-grained PAT",
    ),
    Rule(
        "SLACK-TOKEN",
        re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b"),
        "Slack token",
    ),
    Rule(
        "OPENSSH-PRIVATE-KEY",
        re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----"),  # fpf-secret-scan: allow rule definition
        "OpenSSH private key",
    ),
)

HEX64 = re.compile(r"\b[0-9a-fA-F]{64}\b")
KEY_CONTEXT = re.compile(
    r"(private[_-]?key|seed|secret|signing[_-]?key|issuer[_-]?key)", re.IGNORECASE
)


@dataclass
class Finding:
    path: str
    line: int
    rule_id: str
    note: str
    excerpt: str


def _decode(raw: bytes) -> str | None:
    if b"\x00" in raw[:4096]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def scan_text(path: str, text: str, *, allow_key_context: bool = True) -> list[Finding]:
    findings: list[Finding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if SUPPRESS_MARKER in line:
            continue
        for rule in RULES:
            match = rule.pattern.search(line)
            if match and match.group(0) not in ALLOWED_EXACT:
                findings.append(
                    Finding(path, number, rule.rule_id, rule.note, line.strip()[:120])
                )
        hex_match = HEX64.search(line) if allow_key_context else None
        if hex_match and KEY_CONTEXT.search(line) and hex_match.group(0) not in ALLOWED_EXACT:
            findings.append(
                Finding(
                    path,
                    number,
                    "HEX64-KEY-CONTEXT",
                    "64-hex value next to key material wording",
                    line.strip()[:120],
                )
            )
    return findings


def scan_file(path: Path, display: str) -> list[Finding]:
    try:
        if path.stat().st_size > MAX_BYTES:
            return []
        raw = path.read_bytes()
    except OSError:
        return []
    text = _decode(raw)
    if text is None:
        return []
    return scan_text(display, text)


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit("git command failed: git " + " ".join(args))
    return result.stdout


def tracked_paths() -> list[str]:
    return [p for p in _git("ls-files", "-z").split("\x00") if p]


def staged_paths() -> list[str]:
    out = _git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z")
    return [p for p in out.split("\x00") if p]


def staged_blob(path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f":{path}"], capture_output=True, check=False
    )
    if result.returncode != 0:
        return None
    return _decode(result.stdout)


def scan_staged() -> list[Finding]:
    findings: list[Finding] = []
    for path in staged_paths():
        text = staged_blob(path)
        if text is None:
            continue
        findings.extend(scan_text(path, text))
    return findings


def scan_tracked() -> list[Finding]:
    findings: list[Finding] = []
    for path in tracked_paths():
        findings.extend(scan_file(Path(path), path))
    return findings


def scan_tree(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        findings.extend(scan_file(path, str(path.relative_to(root)).replace("\\", "/")))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic repository secret scan")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--staged", action="store_true", help="scan staged blobs only")
    group.add_argument("--tracked", action="store_true", help="scan tracked files (default)")
    group.add_argument("--path", help="scan a directory tree")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    if args.path:
        findings = scan_tree(Path(args.path))
    elif args.staged:
        findings = scan_staged()
    else:
        findings = scan_tracked()

    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2, ensure_ascii=False))
    else:
        for finding in findings:
            print(
                f"[SECRET] {finding.path}:{finding.line} {finding.rule_id} "
                f"({finding.note}) :: {finding.excerpt}"
            )
        if findings:
            print(f"\n{len(findings)} finding(s). Commit blocked.", file=sys.stderr)

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
