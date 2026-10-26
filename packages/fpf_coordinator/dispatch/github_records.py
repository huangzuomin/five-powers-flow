"""Read canonical GitHub records; never equate PR text with authenticated QA.

The caller supplies GitHub API payloads and an explicit scope authorization.
Authenticating that human authorization against GitHub permissions is an
external deployment requirement. QA PASS additionally needs a trusted,
external GitHub Action/review/evidence evaluator, not just this parser.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Callable
import yaml
import jsonschema
from packages.fpf_coordinator import coordinator as trusted
from .core import CanonicalSnapshot, canonical_url, sha


def parse_card(body: str, kind: str) -> dict | None:
    raw = trusted.extract_yaml_block(body or "", marker=kind)
    if not raw:
        return None
    parsed = yaml.safe_load(raw)
    if not isinstance(parsed, dict) or parsed.get("kind") != kind:
        raise ValueError("Invalid canonical " + kind + " YAML")
    return parsed


def from_github_records(
    issue: dict, pr: dict | None, *,
    baseline_sha: str, project_id: str, repo_path: Path | None = None,
    scope_authorized: bool = False, reviews: list[dict] | None = None,
    authenticate_qa_pass: Callable[[dict, dict, list[dict]], bool] | None = None,
    attempt: int = 1, max_attempts: int = 3,
) -> CanonicalSnapshot:
    """Separate GitHub record parsing from external identity/evidence trust.

    Do not pass an arbitrary unverified True for scope_authorized or
    authenticate_qa_pass: they are gateway attestation inputs.
    """
    url = canonical_url(str(issue.get("html_url") or ""))
    if not url.split("/")[-2] == "issues":
        raise ValueError("Expected canonical GitHub Issue")
    work = parse_card(str(issue.get("body") or ""), "WORK_ORDER")
    if work is None:
        raise ValueError("GitHub Issue lacks WORK_ORDER; cannot dispatch")
    schema_path = Path(__file__).resolve().parents[3] / "schemas" / "work-order.schema.json"
    if not schema_path.is_file():
        raise ValueError("Trusted WORK_ORDER schema missing; refusing to skip")
    jsonschema.Draft7Validator(json.loads(schema_path.read_text(encoding="utf-8"))).validate(work)
    task = str(work["task_id"])
    baseline = sha(baseline_sha)
    revision = str(issue.get("updated_at") or "")
    if not revision:
        raise ValueError("Missing GitHub Issue revision")
    bounds = work.get("boundaries") or {}
    scope = str(work["objective"])
    acceptance = tuple(work["acceptance_criteria"])
    allowed_paths = tuple(bounds.get("allowed_paths") or ())
    dev = None
    dev_valid = False
    qa = None
    qa_authenticated = False
    pr_head = None
    if pr is not None:
        pr_url = canonical_url(str(pr.get("html_url") or ""))
        if pr_url.split("/")[-2] != "pull" or pr_url.split("/")[3:5] != url.split("/")[3:5]:
            # compare canonical GitHub repository (owner/repo), not PR number
            if "/".join(pr_url.split("/")[3:5]) != "/".join(url.split("/")[3:5]):
                raise ValueError("PR belongs to a different GitHub repository")
        pr_head = sha(str((pr.get("head") or {}).get("sha") or ""))
        dev = parse_card(str(pr.get("body") or ""), "DEV_HANDOFF")
        if dev is not None:
            errors = trusted.validate_dev_handoff(dev,repo_path=repo_path)
            dev_valid = not errors and all((
                str(dev.get("task_id")) == task,
                str(dev.get("author") or "").casefold() ==
                    str((pr.get("user") or {}).get("login") or "").casefold(),
                bool(str((pr.get("user") or {}).get("login") or "").strip()),
                str(dev.get("tested_code_sha") or "").lower() == pr_head,
                str(dev.get("baseline_sha") or "").lower() == baseline,
                str(dev.get("pr_url") or "") == pr_url,
                str(dev.get("state") or "") == "DEV_READY_FOR_QA",
            ))
            # If we cannot check the real Git commit objects, do not
            # promote DEV based on self-reported SHA alone.
            if repo_path is None:
                dev_valid = False
        latest = {}
        for review in reviews or []:
            login = str((review.get("user") or {}).get("login") or "").casefold()
            if login:
                latest[login] = review
        for login, review in latest.items():
            candidate = parse_card(str(review.get("body") or ""), "QA_RESULT")
            if (candidate is None or str(candidate.get("task_id") or "") != task or
                    str(candidate.get("tested_sha") or "").lower() != pr_head or
                    str(candidate.get("author") or "").casefold() != login or
                    login == str((pr.get("user") or {}).get("login") or "").casefold() or
                    str(review.get("commit_id") or "").lower() != pr_head):
                continue
            qa = candidate
            if candidate.get("verdict") == "FAIL" and review.get("state") == "CHANGES_REQUESTED":
                # Rework is safe to propose on authenticated adverse feedback.
                # This never attests PASS or verifies EVID artifacts.
                qa_authenticated = True
            elif candidate.get("verdict") == "PASS" and review.get("state") == "APPROVED":
                if authenticate_qa_pass is not None:
                    qa_authenticated = authenticate_qa_pass(pr,candidate,reviews or []) is True
            break
        revision = revision + "|" + pr_head
    return CanonicalSnapshot(
        task_id=task,project_id=project_id,record_url=url,revision=revision,
        baseline_sha=baseline,pr_head_sha=pr_head,scope=scope,
        acceptance=acceptance,allowed_paths=allowed_paths,
        scope_authorized=scope_authorized,has_work_order=True,
        dev_card=dev,dev_validated=dev_valid,
        qa_card=qa,qa_authenticated=qa_authenticated,
        attempt=attempt,max_attempts=max_attempts)
