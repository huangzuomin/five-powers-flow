"""Github-authenticated, content-bound scope-grant events.

Approval is a platform-authenticated human comment, not a cryptographic
signature. The caller must read comments through the authenticated GitHub API
and configure approvers independently of the Issue body.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import re
from .core import canonical_url, sha
from packages.fpf_coordinator.coordinator import extract_yaml_block
import yaml


@dataclass(frozen=True)
class ScopeGrant:
    comment_id: int
    actor: str
    task_id: str
    project_id: str
    issue_url: str
    work_order_sha256: str
    issue_revision: str
    baseline_sha: str
    target_branch: str
    max_attempts: int

    def matches(self, issue: dict, work: dict, *, project_id: str, baseline_sha: str) -> bool:
        return all((
            self.issue_url == canonical_url(str(issue.get("html_url") or "")),
            self.task_id == work.get("task_id"),
            self.project_id == project_id,
            self.work_order_sha256 == hashlib.sha256(
                str(issue.get("body") or "").encode("utf-8")).hexdigest(),
            self.issue_revision == str(issue.get("updated_at") or ""),
            self.baseline_sha == sha(baseline_sha),
            self.target_branch == str(work.get("target_branch") or ""),
            1 <= self.max_attempts <= 10
        ))


def resolve_scope_grant(issue: dict, work: dict, *, comments: list[dict],
                        authorized_actor: str, project_id: str,
                        baseline_sha: str) -> ScopeGrant | None:
    """A later revocation cancels a grant. A changed Issue requires a new grant.

    The platform-authenticated author is from comment.user.login, NEVER a
    self-attested YAML field. Comments must be supplied in GitHub ascending
    order and include immutable numeric IDs. No Issue-creator shortcut.
    """
    if not authorized_actor or not re.fullmatch(r"[A-Za-z0-9_-]{1,39}", authorized_actor):
        raise ValueError("Explicit current project approver required")
    last_id = 0
    selected = None
    for comment in comments:
        ident = comment.get("id")
        if not isinstance(ident, int) or ident <= last_id:
            raise ValueError("GitHub comments not in monotonic ID order")
        last_id = ident
        if str((comment.get("user") or {}).get("login") or "").casefold() != authorized_actor.casefold():
            continue
        body = str(comment.get("body") or "")
        for kind in ("FPF_SCOPE_GRANT", "FPF_SCOPE_REVOKE"):
            block = extract_yaml_block(body, marker=kind)
            if not block:
                continue
            event = yaml.safe_load(block)
            if not isinstance(event, dict) or event.get("kind") != kind:
                raise ValueError("Malformed scope event")
            if canonical_url(str(event.get("issue_url") or "")) != canonical_url(
                    str(issue.get("html_url") or "")):
                continue
            if kind == "FPF_SCOPE_REVOKE":
                selected = None
                continue
            if str(event.get("grant_version")) != "1":
                raise ValueError("Unsupported scope grant version")
            grant = ScopeGrant(
                comment_id=ident, actor=authorized_actor,
                task_id=str(event.get("task_id") or ""),
                project_id=str(event.get("project_id") or ""),
                issue_url=canonical_url(str(event["issue_url"])),
                work_order_sha256=str(event.get("work_order_sha256") or "").lower(),
                issue_revision=str(event.get("issue_revision") or ""),
                baseline_sha=sha(str(event.get("baseline_sha") or "")),
                target_branch=str(event.get("target_branch") or ""),
                max_attempts=event.get("max_attempts"))
            if (not isinstance(grant.max_attempts,int) or isinstance(grant.max_attempts,bool)
                    or not 1 <= grant.max_attempts <= 10):
                raise ValueError("Grant attempt limit must be 1..10")
            if not re.fullmatch(r"[a-f0-9]{64}", grant.work_order_sha256):
                raise ValueError("Malformed work order digest")
            selected = grant
    if selected and selected.matches(issue, work, project_id=project_id,
                                     baseline_sha=baseline_sha):
        return selected
    return None
