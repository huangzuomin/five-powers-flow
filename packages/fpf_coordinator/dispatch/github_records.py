"""GitHub-sourced WORK_ORDER / DEV_HANDOFF / QA_RESULT validation.

A YAML card is not evidence. Scope authority is an authenticated current
ScopeGrant bound to exact Issue body; the PR base/head and changed paths are
checked against actual Git objects before dispatching independent QA.
"""
from __future__ import annotations
from pathlib import Path
import json
import subprocess
from typing import Callable
import yaml
import jsonschema
from packages.fpf_coordinator import coordinator as trusted
from packages.fpf_policy.protected import normalize_repo_path
from .core import CanonicalSnapshot, canonical_url, sha
from .scope_grant import ScopeGrant


def parse_card(body: str, kind: str) -> dict | None:
    raw = trusted.extract_yaml_block(body or "", marker=kind)
    if not raw:
        return None
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict) or parsed.get("kind") != kind:
        raise ValueError("Invalid canonical " + kind + " YAML")
    return parsed


def _changed_paths(repo: Path, base: str, head: str) -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--no-renames", "--name-only", "-z", base + ".." + head],
        cwd=repo, capture_output=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError("Could not verify actual Git diff; refusing QA dispatch")
    try:
        return {normalize_repo_path(s.decode("utf-8", "strict"))
                for s in result.stdout.split(b"\x00") if s}
    except UnicodeDecodeError as exc:
        raise ValueError("Non-UTF8 changed filename requires manual review") from exc


def _within_scope(path: str, allowed_paths: tuple[str, ...]) -> bool:
    for raw in allowed_paths:
        prefix = raw.replace("\\", "/").endswith("/")
        allowed = normalize_repo_path(raw.rstrip("/\\"))
        if path == allowed or (prefix and path.startswith(allowed + "/")):
            return True
    return False


def _merge_verified(pr: dict, baseline: str, repo_path: Path | None) -> bool:
    """A verified GitHub PR merge plus locally reachable merged commit.

    A local checked-out default branch is required; squash merges are valid
    when GitHub reports its actual merge commit and it is on that branch.
    """
    if not (pr.get("merged") is True and pr.get("merged_at") and repo_path):
        return False
    candidate = (pr.get("merge_commit") or {}).get("sha")
    branch = str((pr.get("base") or {}).get("ref") or "")
    if not candidate or not branch or any(x in branch for x in ("..", " ", "~", "^", ":", "\\")):
        return False
    try:
        merge_sha = sha(candidate)
        verify = lambda args: subprocess.run(
            ["git", *args], cwd=repo_path, capture_output=True, check=False, timeout=30)
        if verify(["cat-file", "-t", merge_sha]).stdout.strip() != b"commit":
            return False
        if verify(["merge-base", "--is-ancestor", baseline, merge_sha]).returncode:
            return False
        # Candidate branch is not considered a trusted default-branch checkout.
        for reference in ("refs/remotes/origin/" + branch, "refs/heads/" + branch):
            rev = verify(["rev-parse", "--verify", reference])
            if rev.returncode == 0 and verify(
                    ["merge-base", "--is-ancestor", merge_sha, reference]).returncode == 0:
                return True
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False
    return False


def from_github_records(
    issue: dict, pr: dict | None, *,
    baseline_sha: str, project_id: str, repo_path: Path | None = None,
    scope_grant: ScopeGrant | None = None,
    reviews: list[dict] | None = None,
    authenticate_qa_pass: Callable[[dict, dict, list[dict]], bool] | None = None,
    authenticate_qa_failure: Callable[[dict, dict, list[dict]], bool] | None = None,
    evidence_dir: Path | None = None,
    attempt: int = 1,
) -> CanonicalSnapshot:
    url = canonical_url(str(issue.get("html_url") or ""))
    if url.split("/")[-2] != "issues":
        raise ValueError("Expected canonical GitHub Issue")
    work = parse_card(str(issue.get("body") or ""), "WORK_ORDER")
    if work is None:
        raise ValueError("GitHub Issue lacks WORK_ORDER; cannot dispatch")
    schema_path = Path(__file__).resolve().parents[3] / "schemas/work-order.schema.json"
    if not schema_path.is_file():
        raise ValueError("Trusted WORK_ORDER schema missing")
    jsonschema.Draft7Validator(json.loads(schema_path.read_text(encoding="utf-8"))).validate(work)
    baseline = sha(baseline_sha)
    revision = str(issue.get("updated_at") or "")
    if not revision:
        raise ValueError("Missing canonical Issue revision")
    bounds = work.get("boundaries") or {}
    allowed = tuple(bounds.get("allowed_paths") or ())
    grant_ok = (scope_grant is not None and isinstance(scope_grant, ScopeGrant)
                and scope_grant.matches(issue, work, project_id=project_id,
                                        baseline_sha=baseline))
    # A bool or Issue creator string cannot certify a current grant.
    dev = None
    dev_valid = False
    qa = None
    qa_authenticated = False
    head = None
    merged = False
    if pr is not None:
        pr_url = canonical_url(str(pr.get("html_url") or ""))
        if pr_url.split("/")[-2] != "pull" or pr_url.split("/")[3:5] != url.split("/")[3:5]:
            raise ValueError("Expected PR belonging to the same GitHub repository")
        head = sha(str((pr.get("head") or {}).get("sha") or ""))
        base = str((pr.get("base") or {}).get("sha") or "").lower()
        branch = str((pr.get("head") or {}).get("ref") or "")
        # No alternate caller baseline or unapproved branch may shrink diff.
        base_valid = base == baseline and bool(scope_grant) and grant_ok
        branch_valid = branch == str(work.get("target_branch") or "")
        dev = parse_card(str(pr.get("body") or ""), "DEV_HANDOFF")
        if dev is not None and repo_path is not None and base_valid and branch_valid:
            errors = trusted.validate_dev_handoff(dev, repo_path=repo_path)
            try:
                physical_paths = _changed_paths(repo_path, baseline, head)
                in_scope = (bool(physical_paths) and
                            all(_within_scope(p, allowed) for p in physical_paths))
            except (OSError, subprocess.TimeoutExpired, ValueError):
                in_scope = False
            dev_valid = (not errors and in_scope and all((
                str(dev.get("task_id")) == str(work["task_id"]),
                str(dev.get("author") or "").casefold() ==
                    str((pr.get("user") or {}).get("login") or "").casefold(),
                bool(str((pr.get("user") or {}).get("login") or "").strip()),
                str(dev.get("tested_code_sha") or "").lower() == head,
                str(dev.get("baseline_sha") or "").lower() == baseline,
                str(dev.get("pr_url") or "") == pr_url,
                str(dev.get("state") or "") == "DEV_READY_FOR_QA",
            )))
        if not base_valid or not branch_valid:
            # The draft may be visible, but no next-role dispatch is legal.
            dev_valid = False
        latest = {}
        for review in reviews or []:
            login = str((review.get("user") or {}).get("login") or "").casefold()
            if login:
                latest[login] = review
        for login, review in latest.items():
            candidate = parse_card(str(review.get("body") or ""), "QA_RESULT")
            if (candidate is None or str(candidate.get("task_id") or "") != str(work["task_id"]) or
                    str(candidate.get("tested_sha") or "").lower() != head or
                    str(candidate.get("author") or "").casefold() != login or
                    login == str((pr.get("user") or {}).get("login") or "").casefold() or
                    str(review.get("commit_id") or "").lower() != head):
                continue
            qa = candidate
            if not dev_valid or repo_path is None:
                break
            verdict = candidate.get("verdict")
            review_state = str(review.get("state") or "").upper()
            # FAIL also requires a complete QA_RESULT and actual independent
            # test artifact. A 4-field CHANGES_REQUESTED is NOT enough.
            authority = (authenticate_qa_failure if verdict == "FAIL" else
                         authenticate_qa_pass if verdict == "PASS" else None)
            if authority is not None and evidence_dir is not None and (
                    (verdict == "FAIL" and review_state == "CHANGES_REQUESTED") or
                    (verdict == "PASS" and review_state == "APPROVED")):
                errs = trusted.validate_qa_result(
                    candidate, dev_data=dev, repo_path=repo_path,
                    evidence_dir=evidence_dir)
                if not errs:
                    qa_authenticated = authority(pr, candidate, reviews or []) is True
            break
        merged = bool(qa_authenticated and qa and qa.get("verdict") == "PASS"
                      and _merge_verified(pr, baseline, repo_path))
        revision = revision + "|" + head
    return CanonicalSnapshot(
        task_id=str(work["task_id"]), project_id=project_id, record_url=url,
        revision=revision, baseline_sha=baseline, pr_head_sha=head,
        scope=str(work["objective"]), acceptance=tuple(work["acceptance_criteria"]),
        allowed_paths=allowed, scope_authorized=grant_ok,
        has_work_order=True, dev_card=dev, dev_validated=dev_valid,
        qa_card=qa, qa_authenticated=qa_authenticated,
        pr_merge_authenticated=merged, attempt=attempt,
        max_attempts=scope_grant.max_attempts if grant_ok else 1)
