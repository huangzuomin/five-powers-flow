"""GitHub PR gate: role routing and platform-authenticated review provenance.

This verifies GitHub platform review identity, not physical EVID evidence origin.
The latter requires a separately signed QA runner/artifact integration.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request, urlopen

import yaml
from packages.fpf_coordinator import coordinator
from packages.fpf_policy.protected import is_protected, normalize_repo_path

BOOT_FILES = frozenset({
    "agents.md", "docs/coordination/project-map.md",
    "docs/coordination/lessons.md",
    "docs/coordination/handoff-protocol.md",
    ".claude/settings.json", ".github/codeowners",
})
MAP_FILES = frozenset({"project-map.md", "lessons.md",
                       "docs/coordination/project-map.md",
                       "docs/coordination/lessons.md"})


def classify(paths: list[str], kind: str, baseline_files: set[str],
             branch: str) -> str:
    changed = [normalize_repo_path(p) for p in paths]
    if not changed or len(changed) != len(set(changed)):
        raise ValueError("Missing or duplicate changed paths")
    changed_set = set(changed)
    baseline_files = {normalize_repo_path(p) for p in baseline_files}
    if kind == "BOOTSTRAP":
        if not branch.startswith("fpf/bootstrap-"):
            raise ValueError("BOOTSTRAP must originate from a bootstrap branch")
        allowed = lambda p: (p in BOOT_FILES or p.startswith((
            ".fpf/", "schemas/", ".github/workflows/")))
        if any(not allowed(p) for p in changed_set):
            raise ValueError("BOOTSTRAP contains application code / unauthorized path")
        if not {"agents.md","docs/coordination/project-map.md",
                ".fpf/project.yaml"}.issubset(changed_set):
            raise ValueError("BOOTSTRAP missing required initial governance artifacts")
        if any(p in baseline_files for p in changed_set):
            raise ValueError("BOOTSTRAP cannot overwrite existing baseline files")
        return "BOOTSTRAP_PR"
    if kind == "POLICY_CHANGE":
        # Changes to protected gate definitions are not normal CODE_PR.
        return "POLICY_PR"
    if kind == "MAP_UPDATE":
        if changed_set - MAP_FILES:
            raise ValueError("MAP_PR contains non-map paths")
        return "MAP_PR"
    if kind == "DEV_HANDOFF":
        forbidden = [p for p in changed if is_protected(p)]
        if forbidden:
            raise ValueError("CODE_PR modifies protected governance paths: " + str(forbidden))
        return "CODE_PR"
    raise ValueError("Unknown PR kind")


def yaml_card(body: str, wanted: str) -> dict:
    text = coordinator.extract_yaml_block(body, marker=wanted)
    if not text:
        raise ValueError("Missing YAML card kind: " + wanted)
    card = yaml.safe_load(text)
    if not isinstance(card, dict) or card.get("kind") != wanted:
        raise ValueError("Invalid " + wanted + " card")
    return card


def verified_reviewer(reviews: list[dict], pr_author: str, sha: str) -> tuple[str, dict]:
    """Newest review *value* per authenticated login controls approval."""
    latest = {}
    for item in reviews:
        actor = str((item.get("user") or {}).get("login") or "").casefold()
        if actor:
            latest[actor] = item
    for actor, review in latest.items():
        if actor == pr_author.casefold():
            continue
        if str(review.get("state")).upper() != "APPROVED":
            continue
        if str(review.get("commit_id") or "").lower() != sha.lower():
            continue
        try:
            qa = yaml_card(review.get("body") or "", "QA_RESULT")
        except (ValueError, yaml.YAMLError):
            continue
        if str(qa.get("author") or "").casefold() != actor:
            continue
        if str(qa.get("tested_sha") or "").lower() != sha.lower():
            continue
        if str(qa.get("verdict")) != "PASS":
            continue
        if str(qa.get("task_id") or "") == "":
            continue
        return actor, qa
    raise ValueError("No distinct GitHub-authenticated APPROVED QA_RESULT on current head SHA")


def authenticated_approval(reviews: list[dict], pr_author: str,
                           sha: str) -> str:
    """For non-code PRs, use latest authenticated review value per login."""
    latest = {}
    for review in reviews:
        actor = str((review.get("user") or {}).get("login") or "").casefold()
        if actor:
            latest[actor] = review
    for actor, review in latest.items():
        if actor != pr_author.casefold() and (
            str(review.get("state") or "").upper() == "APPROVED"
            and str(review.get("commit_id") or "").lower() == sha.lower()
        ):
            return actor
    raise ValueError("Independent platform APPROVED review on current head is required")


def gh_reviews(repo_slug: str, pr_num: int, token: str) -> list[dict]:
    if not token:
        raise ValueError("GitHub read token required")
    all_reviews = []
    for page in range(1, 101):
        url = (f"https://api.github.com/repos/{repo_slug}/pulls/{pr_num}/reviews"
               f"?per_page=100&page={page}")
        req = Request(url, headers={"Authorization": "Bearer " + token,
                                    "Accept": "application/vnd.github+json"})
        with urlopen(req, timeout=25) as resp:
            data = json.load(resp)
        if not isinstance(data, list) or len(data) > 100:
            raise ValueError("Invalid GitHub reviews page " + str(page))
        all_reviews.extend(data)
        if len(data) < 100:
            return all_reviews
    raise ValueError("Review pagination exceeded 10000 items; audit required")


def git_cmd(*args: str) -> str:
    p = subprocess.run(["git", *args], capture_output=True, text=True,
                       timeout=30, cwd=os.environ.get("GITHUB_WORKSPACE") or None,
                       check=False)
    if p.returncode:
        raise ValueError("Git verification error: " + p.stderr[-400:])
    return p.stdout.strip()


def evaluate(event: dict, reviews: list[dict], files: list[str],
             baseline_files: set[str]) -> str:
    pr = event.get("pull_request") or {}
    sha = str((pr.get("head") or {}).get("sha") or "").lower()
    base = str((pr.get("base") or {}).get("sha") or "").lower()
    author = str((pr.get("user") or {}).get("login") or "")
    branch = str((pr.get("head") or {}).get("ref") or "")
    if not (coordinator.HEX_SHA_RE.fullmatch(sha) and coordinator.HEX_SHA_RE.fullmatch(base)
            and author):
        raise ValueError("Missing authenticated PR metadata or SHA")
    body = str(pr.get("body") or "")
    cards = []
    for kind in ("DEV_HANDOFF","MAP_UPDATE","BOOTSTRAP","POLICY_CHANGE"):
        if coordinator.extract_yaml_block(body,kind):
            cards.append(kind)
    if len(cards) != 1:
        raise ValueError("Exactly one PR kind card must be present")
    kind = cards[0]
    card = yaml_card(body,kind)
    pr_type = classify(files,kind,baseline_files,branch)
    reviewer = authenticated_approval(reviews, author, sha)
    if pr_type == "CODE_PR":
        reviewer, qa = verified_reviewer(reviews, author, sha)
        if str(card.get("author") or "").casefold() != author.casefold():
            raise ValueError("DEV_HANDOFF.author must equal platform PR author")
        if str(card.get("tested_code_sha") or "").lower() != sha:
            raise ValueError("DEV_HANDOFF head SHA mismatch")
        errs = coordinator.validate_dev_handoff(
            card, repo_path=Path(os.environ.get("GITHUB_WORKSPACE") or Path.cwd()))
        if errs:
            raise ValueError("DEV_HANDOFF invalid: " + "; ".join(errs))
        if str(qa.get("task_id")) != str(card.get("task_id")):
            raise ValueError("QA_RESULT and DEV_HANDOFF task_id mismatch")
        if str(qa.get("runner_sha")) == sha or str(qa.get("qa_contract_sha")) == sha:
            raise ValueError("QA toolchain must be pinned independently of PR tested code")
        from packages.fpf_policy.qa_artifact import independent_qa_evidence
        repo_dir = Path(os.environ.get("GITHUB_WORKSPACE") or Path.cwd())
        with independent_qa_evidence(
            repo=os.environ["GITHUB_REPOSITORY"], qa=qa,
            reviewer=reviewer, tested_sha=sha,
            task_id=str(card["task_id"]),
            token=os.environ.get("GH_TOKEN", ""),
            repository_dir=repo_dir,
        ) as evidence_dir:
            qa_errors = coordinator.validate_qa_result(
                qa, dev_data=card, repo_path=repo_dir,
                evidence_dir=evidence_dir,
            )
            if qa_errors:
                raise ValueError("QA_RESULT rejected: " + "; ".join(qa_errors))
        return "CODE_PR: GitHub-authenticated independent review and artifact verified"
    if pr_type == "BOOTSTRAP_PR":
        if str(card.get("baseline_sha")).lower() != base:
            raise ValueError("BOOTSTRAP baseline != PR base SHA")
        if str(card.get("project_id") or "") == "":
            raise ValueError("BOOTSTRAP project_id missing")
    if pr_type == "MAP_PR":
        code_sha = str(card.get("code_merged_sha") or "")
        if not coordinator.HEX_SHA_RE.fullmatch(code_sha):
            raise ValueError("MAP_UPDATE code_merged_sha is not a commit")
        if subprocess.run(["git","merge-base","--is-ancestor",code_sha,base],
                          check=False).returncode:
            raise ValueError("MAP_UPDATE code_merged_sha is not merged into target base")
    if pr_type == "POLICY_PR" and str(card.get("risk_acknowledged")).lower() != "true":
        raise ValueError("POLICY_CHANGE must explicitly acknowledge governance risk")
    return pr_type + " independently reviewed by " + reviewer + " (identity only)"


def main() -> int:
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        pr = event["pull_request"]
        sha = pr["head"]["sha"]
        base = pr["base"]["sha"]
        files = git_cmd("diff","--name-only",base+"..."+sha).splitlines()
        tracked = set(git_cmd("ls-tree","-r","--name-only",base).splitlines())
        repo_slug = os.environ["GITHUB_REPOSITORY"]
        reviews = gh_reviews(repo_slug,int(pr["number"]),os.environ.get("GH_TOKEN",""))
        print(evaluate(event,reviews,files,tracked))
        return 0
    except Exception as exc:
        print("::error::[FPF FAIL CLOSED] " + str(exc),file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
