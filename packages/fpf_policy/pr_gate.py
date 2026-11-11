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
from packages.fpf_policy import stations

BOOT_FILES = frozenset({
    "agents.md", "docs/coordination/project-map.md",
    "docs/coordination/lessons.md",
    "docs/coordination/handoff-protocol.md",
    ".claude/settings.json", ".github/codeowners",
})
MAP_FILES = frozenset({"project-map.md", "lessons.md",
                       "docs/coordination/project-map.md",
                       "docs/coordination/lessons.md"})
# Governed location of normative standard text. The location *is* the contract:
# a change that touches this tree (including by rename or deletion) must be
# adjudicated through the independent-QA route, never an identity-only one.
#
# Governance rule: normative text lives under docs/standards/. A document kept
# elsewhere is by definition not normative and does not carry the DOC gate; if
# something needs that status it must be moved here, which is itself gated.
NORMATIVE_STANDARD_PREFIX = "docs/standards/"


def is_normative_standard(path: str) -> bool:
    """Any file in the governed tree, regardless of extension."""
    try:
        normalized = normalize_repo_path(path)
    except ValueError:
        return False
    return normalized.startswith(NORMATIVE_STANDARD_PREFIX)

def _policy_scope(changed: set[str]) -> str:
    """Governing workflow changes require the GATE_PR route, never prose waiver."""
    prose = {"readme.md", "changelog.md", "contributing.md", "security.md", ".gitignore", "license", "pyproject.toml"}
    if any(not (p in prose or p.startswith(("docs/", "tests/", "templates/"))
                or is_protected(p)) for p in changed):
        raise ValueError("POLICY_CHANGE contains unrelated application files")
    if any(is_protected(p) or p.startswith(("tests/", "templates/")) for p in changed):
        return "GATE_PR"
    return "POLICY_PR"

def _exact_card_diff(card: dict, files: list[str], sha: str, base: str) -> None:
    if str(card.get("tested_code_sha") or "").lower() != sha:
        raise ValueError("POLICY_CHANGE tested_code_sha must equal authenticated PR HEAD")
    if str(card.get("baseline_sha") or "").lower() != base:
        raise ValueError("POLICY_CHANGE baseline_sha must equal authenticated PR base")
    listed = card.get("changed_files")
    if not isinstance(listed, list) or not all(isinstance(x, str) for x in listed):
        raise ValueError("POLICY_CHANGE changed_files required")
    if len(listed) != len(set(listed)) or set(map(normalize_repo_path, listed)) != set(map(normalize_repo_path, files)):
        raise ValueError("POLICY_CHANGE changed_files differ from authenticated Git diff")



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
        has_agents = "agents.md" in changed_set or "agents.md" in baseline_files
        has_map = ("docs/coordination/project-map.md" in changed_set or
                   "docs/project-map.md" in baseline_files or
                   "docs/coordination/project-map.md" in baseline_files)
        if not (has_agents and has_map and ".fpf/project.yaml" in changed_set):
            raise ValueError("BOOTSTRAP missing required initial governance artifacts")
        if any(p in baseline_files for p in changed_set):
            raise ValueError("BOOTSTRAP cannot overwrite existing baseline files")
        return "BOOTSTRAP_PR"
    if kind == "POLICY_CHANGE":
        return _policy_scope(changed_set)
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
        qa_author = str(qa.get("author") or "").casefold()
        if qa_author not in (actor, actor.removesuffix("[bot]")):
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
                       timeout=30, cwd=os.environ.get("FPF_CANDIDATE_REPO") or os.environ.get("GITHUB_WORKSPACE") or None,
                       check=False)
    if p.returncode:
        raise ValueError("Git verification error: " + p.stderr[-400:])
    return p.stdout.strip()


def touched_paths(base: str, sha: str, repo_dir: str | None = None) -> set[str]:
    """Every path a change set touches, including rename sources and deletions.

    ``git diff --name-only`` reports only the destination of a rename and drops
    deleted paths entirely, so a file moved out of the governed tree would look
    like an unrelated addition. ``--name-status -M`` keeps the source path.
    """
    if repo_dir is None:
        raw = git_cmd("diff", "--name-status", "-M", f"{base}...{sha}")
    else:
        result = subprocess.run(
            ["git", "diff", "--name-status", "-M", f"{base}...{sha}"],
            cwd=repo_dir, capture_output=True, text=True, timeout=30, check=False,
        )
        if result.returncode:
            raise ValueError("Git verification error: " + result.stderr[-400:])
        raw = result.stdout.strip()
    paths: set[str] = set()
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        for candidate in parts[1:]:
            candidate = candidate.strip()
            if candidate:
                paths.add(candidate)
    return paths


def promote_doc_route(pr_type: str, files, extra_paths=None) -> str:
    """Identity-only routing is not available for normative standard changes.

    Every route that does not already demand independent QA is promoted:
    POLICY_PR and MAP_PR are identity-only, and BOOTSTRAP_PR can add normative
    text without a QA_RESULT. CODE_PR and GATE_PR already require one, so they
    keep their kind and the profile binding decides the rest.

    Promotion runs on the touched set, so renaming a standard into another
    directory (including MAP_FILES) does not launder it into prose.
    """
    if pr_type in ("GATE_PR", "CODE_PR"):
        return pr_type
    touched = {normalize_repo_path(p) for p in files}
    touched |= {normalize_repo_path(p) for p in (extra_paths or set())}
    if any(is_normative_standard(p) for p in touched):
        return "GATE_PR"
    return pr_type


def evaluate(event: dict, reviews: list[dict], files: list[str],
             baseline_files: set[str], extra_paths: set[str] | None = None) -> str:
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
    pr_type = promote_doc_route(pr_type, files, extra_paths)
    repo_dir = Path(os.environ.get("FPF_CANDIDATE_REPO") or os.environ.get("GITHUB_WORKSPACE") or Path.cwd())
    if pr_type in ("CODE_PR", "GATE_PR"):
        reviewer, qa = verified_reviewer(reviews, author, sha)
        # G2: a QA verdict must be signed by a registered qa-evidence station, and
        # the author must never resolve to a QA station. The registry is read from
        # the base commit, so a change set cannot rewrite its own authority.
        registry = stations.load_registry(repo_dir, base)
        qa_station = registry.require(reviewer, {"qa-evidence"}, "QA signer")
        registry.reject_qa_kind(author, "PR author")
    else:
        reviewer = authenticated_approval(reviews, author, sha)
    if pr_type == "GATE_PR":
        _exact_card_diff(card, files, sha, base)
        if card.get("risk_acknowledged") is not True:
            raise ValueError("GATE_PR must explicitly acknowledge policy risk")
        if "sovereign_override" in card:
            raise ValueError(
                "sovereign_override is no longer a substitute for a second independent "
                "approval; remove the field and obtain a second APPROVED review"
            )
        if str(qa.get("task_id")) != str(card.get("task_id")):
            raise ValueError("GATE_PR QA task ID mismatch")
        latest = {}
        for review in reviews:
            actor = str((review.get("user") or {}).get("login") or "").casefold()
            if actor:
                latest[actor] = review
        second = [actor for actor, review in latest.items()
                  if actor not in {author.casefold(), reviewer.casefold()}
                  and str(review.get("state") or "").upper() == "APPROVED"
                  and str(review.get("commit_id") or "").lower() == sha]
        if not second:
            raise ValueError("GATE_PR requires second independent APPROVED review")
        second_station = registry.require(second[0], {"ruling-carrier"}, "second approval")
        if second_station.id == qa_station.id:
            raise ValueError(
                "second approval must come from a station different from the QA signer"
            )
        from packages.fpf_policy.qa_artifact import independent_qa_evidence
        with independent_qa_evidence(repo=os.environ["GITHUB_REPOSITORY"], qa=qa,
                reviewer=reviewer, tested_sha=sha, task_id=str(card["task_id"]),
                token=os.environ.get("GH_TOKEN",""), repository_dir=repo_dir) as evidence_dir:
            errs = coordinator.validate_qa_result(qa, dev_data={
                "task_id":card["task_id"],"author":author,
                "baseline_sha":base,"tested_code_sha":sha},
                repo_path=repo_dir,evidence_dir=evidence_dir)
            if errs:
                raise ValueError("GATE_PR independent QA rejected: " + "; ".join(errs))
        return "GATE_PR independently QA verified and dual-approved"
    if pr_type == "CODE_PR":
        if str(card.get("author") or "").casefold() != author.casefold():
            raise ValueError("DEV_HANDOFF.author must equal platform PR author")
        if str(card.get("tested_code_sha") or "").lower() != sha:
            raise ValueError("DEV_HANDOFF head SHA mismatch")
        errs = coordinator.validate_dev_handoff(
            card, repo_path=repo_dir)
        if errs:
            raise ValueError("DEV_HANDOFF invalid: " + "; ".join(errs))
        if str(qa.get("task_id")) != str(card.get("task_id")):
            raise ValueError("QA_RESULT and DEV_HANDOFF task_id mismatch")
        if str(qa.get("runner_sha")) == sha or str(qa.get("qa_contract_sha")) == sha:
            raise ValueError("QA toolchain must be pinned independently of PR tested code")
        from packages.fpf_policy.qa_artifact import independent_qa_evidence
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
    if pr_type == "POLICY_PR":
        _exact_card_diff(card, files, sha, base)
        if card.get("risk_acknowledged") is not True:
            raise ValueError("POLICY_CHANGE must explicitly acknowledge governance risk")
    return pr_type + " independently reviewed by " + reviewer + " (identity only)"


def main() -> int:
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        pr = event["pull_request"]
        sha = pr["head"]["sha"]
        base = pr["base"]["sha"]
        files = git_cmd("diff","--name-only",base+"..."+sha).splitlines()
        extra_paths = touched_paths(base, sha) - set(files)
        tracked = set(git_cmd("ls-tree","-r","--name-only",base).splitlines())
        repo_slug = os.environ["GITHUB_REPOSITORY"]
        reviews = gh_reviews(repo_slug,int(pr["number"]),os.environ.get("GH_TOKEN",""))
        print(evaluate(event,reviews,files,tracked,extra_paths=extra_paths))
        return 0
    except Exception as exc:
        print("::error::[FPF FAIL CLOSED] " + str(exc),file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
