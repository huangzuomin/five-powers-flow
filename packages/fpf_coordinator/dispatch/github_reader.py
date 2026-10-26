"""Read-only GitHub observer with explicit current owner scope-grant events."""
from __future__ import annotations
import json
from pathlib import Path
import re
import subprocess
from typing import Callable, Any
from .github_records import from_github_records, parse_card
from .scope_grant import resolve_scope_grant
from .journal import DispatchJournal

SLUG = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitHubReadOnlySource:
    def __init__(self, repository: str, executable: str = "gh", timeout: int = 30):
        if not SLUG.fullmatch(repository) or timeout < 1:
            raise ValueError("Expected one verified owner/repo slug")
        self.repository, self.executable, self.timeout = repository, executable, timeout

    def _api(self, endpoint: str) -> Any:
        command = [self.executable, "api", "repos/" + self.repository + "/" + endpoint]
        proc = subprocess.run(command, capture_output=True, text=True,
                              timeout=self.timeout,check=False)
        if proc.returncode:
            raise RuntimeError("Read-only GitHub API unavailable (exit %d)" % proc.returncode)
        try:
            return json.loads(proc.stdout)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid GitHub API JSON response") from exc

    def issue(self, number: int) -> dict:
        if not isinstance(number,int) or number <= 0:
            raise ValueError("Invalid Issue number")
        result = self._api("issues/" + str(number))
        if not isinstance(result,dict) or "pull_request" in result:
            raise ValueError("Expected actual GitHub Issue")
        return result

    def pull(self, number: int) -> dict:
        if not isinstance(number,int) or number <= 0:
            raise ValueError("Invalid PR number")
        result = self._api("pulls/" + str(number))
        if not isinstance(result,dict):
            raise ValueError("Expected GitHub PR payload")
        return result

    def _paged(self, endpoint: str) -> list[dict]:
        out = []
        for page in range(1,101):
            values = self._api("%s?per_page=100&page=%d" % (endpoint,page))
            if not isinstance(values,list) or len(values)>100:
                raise ValueError("Invalid GitHub API page")
            out.extend(values)
            if len(values)<100:
                return out
        raise ValueError("GitHub pagination exceeded 10000 entries; fail closed")

    def reviews(self, number: int) -> list[dict]:
        if not isinstance(number,int) or number <= 0:
            raise ValueError("Invalid PR number")
        return self._paged("pulls/%d/reviews" % number)

    def comments(self, number: int) -> list[dict]:
        if not isinstance(number,int) or number <= 0:
            raise ValueError("Invalid Issue number")
        return self._paged("issues/%d/comments" % number)

    def snapshot(self, *, issue_number: int, pr_number: int | None,
                 project_id: str, baseline_sha: str, approved_owner_login: str,
                 repo_path: Path | None, journal: DispatchJournal | None = None,
                 evidence_dir: Path | None = None,
                 authenticate_qa_pass: Callable[[dict,dict,list[dict]], bool] | None = None,
                 authenticate_qa_failure: Callable[[dict,dict,list[dict]], bool] | None = None):
        issue = self.issue(issue_number)
        work = parse_card(str(issue.get("body") or ""), "WORK_ORDER")
        if work is None:
            raise ValueError("Canonical Issue lacks WORK_ORDER")
        grant = resolve_scope_grant(
            issue, work, comments=self.comments(issue_number),
            authorized_actor=approved_owner_login,project_id=project_id,
            baseline_sha=baseline_sha)
        pr = self.pull(pr_number) if pr_number is not None else None
        reviews = self.reviews(pr_number) if pr_number is not None else []
        snapshot = from_github_records(
            issue, pr, baseline_sha=baseline_sha,project_id=project_id,
            scope_grant=grant,reviews=reviews,repo_path=repo_path,
            evidence_dir=evidence_dir,authenticate_qa_pass=authenticate_qa_pass,
            authenticate_qa_failure=authenticate_qa_failure)
        expected_issue="https://github.com/"+self.repository+"/issues/"+str(issue_number)
        if snapshot.record_url != expected_issue:
            raise ValueError("GitHub Issue is not in configured repository")
        if journal is not None and snapshot.scope_authorized:
            from dataclasses import replace
            attempt = journal.canonical_attempt(snapshot)
            snapshot = replace(snapshot,attempt=attempt)
        return snapshot
