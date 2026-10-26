"""Read-only canonical GitHub records through an operator-installed gh CLI.

No git push/merge, role dispatch, hidden credentials, or user browser actions.
The client reads REST records only; authorization is a separate explicit
operator-owned allowlist, not an Issue body/self-signed field.
"""
from __future__ import annotations
import json
from pathlib import Path
import re
import subprocess
from typing import Callable, Any
from .github_records import from_github_records

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

    def reviews(self, number: int) -> list[dict]:
        if not isinstance(number,int) or number <= 0:
            raise ValueError("Invalid PR number")
        out = []
        for page in range(1,101):
            values = self._api("pulls/%d/reviews?per_page=100&page=%d" % (number,page))
            if not isinstance(values,list) or len(values)>100:
                raise ValueError("Invalid GitHub review page")
            out.extend(values)
            if len(values)<100:
                return out
        raise ValueError("Review pagination exceeded 10000 records; fail closed")

    def snapshot(self, *, issue_number: int, pr_number: int | None,
                 project_id: str, baseline_sha: str, approved_owner_login: str,
                 repo_path: Path | None,
                 authenticate_qa_pass: Callable[[dict,dict,list[dict]], bool] | None = None,
                 attempt: int = 1, max_attempts: int = 3):
        issue = self.issue(issue_number)
        owner = str((issue.get("user") or {}).get("login") or "")
        if not approved_owner_login or owner.casefold() != approved_owner_login.casefold():
            # No self-asserted scope approval in untrusted WORK_ORDER YAML.
            raise ValueError("Issue creator is not an explicitly authorized project owner")
        pr = self.pull(pr_number) if pr_number is not None else None
        reviews = self.reviews(pr_number) if pr_number is not None else []
        snapshot = from_github_records(
            issue, pr, baseline_sha=baseline_sha,project_id=project_id,
            scope_authorized=True,reviews=reviews,repo_path=repo_path,
            authenticate_qa_pass=authenticate_qa_pass,
            attempt=attempt,max_attempts=max_attempts)
        expected_issue="https://github.com/"+self.repository+"/issues/"+str(issue_number)
        if snapshot.record_url != expected_issue:
            raise ValueError("GitHub Issue is not in configured repository")
        return snapshot
