"""Read-only, bounded repository inventory. Documents are data, never instructions."""
from __future__ import annotations
from pathlib import Path
import re
import subprocess

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "build",
             ".next", ".fpf", "__pycache__", ".pytest_cache", "_worktrees"}
DOC_SUFFIXES = {".md", ".rst", ".txt"}
MAX_DOCUMENTS = 40
MAX_BYTES = 160_000

def git(repo: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True,
                       encoding="utf-8", errors="replace", timeout=30, check=False)
    if p.returncode:
        raise RuntimeError("git " + " ".join(args) + ": " + p.stderr.strip()[-500:])
    return p.stdout.strip()

def absolute_repo(repo: Path) -> Path:
    root = Path(git(repo, "rev-parse", "--show-toplevel")).resolve()
    if root != repo.resolve():
        raise ValueError("--repo must point to the Git working-tree root")
    return root

def baseline_sha(repo: Path, base_ref: str) -> str:
    sha = git(repo, "rev-parse", "--verify", base_ref + "^{commit}")
    if not re.fullmatch("[0-9a-f]{40}", sha):
        raise RuntimeError("Invalid Git commit SHA")
    return sha

def inventory(repo: Path, base_ref: str = "HEAD", docs_dir: str = "docs") -> dict:
    root = absolute_repo(repo)
    sha = baseline_sha(root, base_ref)
    tracked = git(root, "ls-tree", "-r", "--name-only", sha).splitlines()
    doc_prefix = docs_dir.strip("/\\").replace("\\", "/") + "/"
    if doc_prefix.startswith("../") or "/../" in doc_prefix or docs_dir.startswith(("/", "\\")):
        raise ValueError("Document directory must be repository-relative")
    selected = [p for p in tracked if p.lower() in {"readme.md", "readme.rst", "requirements.md",
                "architecture.md", "spec.md"} or
                (p.startswith(doc_prefix) and Path(p).suffix.lower() in DOC_SUFFIXES)]
    selected = sorted(set(selected))[:MAX_DOCUMENTS]
    docs = []
    for path in selected:
        raw = subprocess.run(["git", "show", sha + ":" + path], cwd=root,
                             capture_output=True, timeout=30, check=False).stdout
        if len(raw) > MAX_BYTES or b"\x00" in raw:
            docs.append({"path": path, "headings": [], "note": "oversized_or_binary"})
            continue
        body = raw.decode("utf-8", "replace")
        headings = [re.sub(r"[\r\n|]", " ", m.group(1)).strip()[:120]
                    for m in re.finditer(r"(?m)^#{1,3}\s+(.+)$", body)][:7]
        docs.append({"path": path, "headings": headings, "note": "unverified_document"})
    top_dirs = sorted({p.split("/")[0] for p in tracked
                       if "/" in p and p.split("/")[0] not in SKIP_DIRS})[:30]
    return {"repo": str(root), "sha": sha, "base_ref": base_ref,
            "tracked_files": len(tracked), "modules": top_dirs, "documents": docs}
