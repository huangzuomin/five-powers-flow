"""Issue #61: canonical decision -> bounded role dispatch, not QA authority.

A transport receipt and local observations NEVER certify DEV/QA completion.
Trusted GitHub verification remains external to this mechanical reducer.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any
from urllib.parse import urlsplit
from packages.fpf_policy.protected import is_protected, normalize_repo_path

SHA = re.compile(r"^[a-f0-9]{40}$")
TASK = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
ROLES = frozenset({"dev_lead", "qa_lead", "scribe"})
DENIED_ACTIONS = frozenset({
    "merge", "deploy", "publish", "sign_qa", "edit_policy", "write_main",
})
ALLOWED_ACTIONS = {
    "dev_lead": frozenset({"plan", "edit_feature_branch", "report_dev"}),
    "qa_lead": frozenset({"read_only_review", "run_independent_tests", "report_findings"}),
    "scribe": frozenset({"draft_map_pr"}),
}


def sha(value: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value.lower()):
        raise ValueError("A pinned 40-hex Git SHA is required")
    return value.lower()


def canonical_url(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Canonical GitHub URL required")
    parsed = urlsplit(value)
    # No username, password, query, fragment or lookalike hostname.
    bits = parsed.path.strip("/").split("/")
    if (parsed.scheme != "https" or parsed.netloc != "github.com" or
            parsed.query or parsed.fragment or len(bits) != 4 or
            bits[2] not in ("issues", "pull") or not bits[3].isdigit() or
            not all(re.fullmatch(r"[A-Za-z0-9_.-]+", piece)
                    for piece in (bits[0], bits[1]))):
        raise ValueError("Expected https://github.com/owner/repo/issues/N or pull/N")
    return "https://github.com/" + "/".join(bits)


@dataclass(frozen=True)
class Target:
    project_id: str
    role: str
    transport: str
    identity: str
    workspace: str
    approved: bool = False

    def __post_init__(self) -> None:
        if not self.approved or not self.identity.strip() or not self.workspace.strip():
            raise ValueError("Explicitly approved, identified target and workspace required")
        if self.role not in ROLES or self.transport not in ("codex_thread", "chatgpt_web"):
            raise ValueError("Unknown role/transport")
        if not TASK.fullmatch(self.project_id):
            raise ValueError("Invalid project ID")
        if self.transport == "chatgpt_web":
            parsed = urlsplit(self.identity)
            if (parsed.scheme != "https" or parsed.netloc not in
                    ("chatgpt.com", "chat.openai.com") or
                    not re.fullmatch(r"/c/[A-Za-z0-9-]{8,}", parsed.path)
                    or parsed.query or parsed.fragment):
                raise ValueError("Expected explicitly registered ChatGPT conversation URL")
        elif not re.fullmatch(r"[A-Za-z0-9_:-]{8,200}", self.identity):
            raise ValueError("Explicit Codex thread ID required")


@dataclass(frozen=True)
class CanonicalSnapshot:
    task_id: str
    project_id: str
    record_url: str
    revision: str
    baseline_sha: str
    pr_head_sha: str | None
    scope: str
    acceptance: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    scope_authorized: bool
    has_work_order: bool
    dev_card: dict | None = None
    dev_validated: bool = False
    qa_card: dict | None = None
    qa_authenticated: bool = False
    pr_merge_authenticated: bool = False
    attempt: int = 1
    max_attempts: int = 3
    scope_grant_id: int = 0

    def __post_init__(self) -> None:
        if not TASK.fullmatch(self.task_id) or not TASK.fullmatch(self.project_id):
            raise ValueError("Invalid task/project ID")
        canonical_url(self.record_url)
        sha(self.baseline_sha)
        if self.pr_head_sha is not None:
            sha(self.pr_head_sha)
        if not self.revision.strip() or not self.scope.strip():
            raise ValueError("Canonical source revision and scope required")
        if not self.acceptance or any(not isinstance(x, str) or not x.strip() for x in self.acceptance):
            raise ValueError("Nonempty acceptance requirements required")
        if not self.allowed_paths or any(
                not isinstance(x, str) or not x.strip() or x.startswith("/")
                or ".." in x.replace("\\", "/").split("/") for x in self.allowed_paths):
            raise ValueError("Approved safe allowed_paths required")
        if not (1 <= self.attempt <= self.max_attempts <= 10):
            raise ValueError("Invalid bounded attempt policy")


@dataclass(frozen=True)
class Decision:
    phase: str
    role: str | None
    reason: str


def next_action(state: CanonicalSnapshot) -> Decision:
    """Conservative reducer; valid_* flags MUST be issued by trusted gateway.

    Raw GitHub YAML content is NOT an attestation. A caller must validate the
    DEV card with coordinator and QA review+artifact through trusted gate.
    """
    if not state.scope_authorized:
        return Decision("HUMAN_GATE_SCOPE", None, "Missing authenticated scope approval")
    if not state.has_work_order:
        return Decision("BLOCKED", None, "Canonical WORK_ORDER absent")
    dev = state.dev_card
    if dev is None:
        return Decision("DISPATCH", "dev_lead", "Authorized work order awaiting DEV")
    if not state.dev_validated:
        return Decision("BLOCKED", None, "DEV_HANDOFF has no trusted validation")
    if not state.pr_head_sha or str(dev.get("tested_code_sha", "")).lower() != state.pr_head_sha.lower():
        return Decision("BLOCKED", None, "Stale DEV tested SHA vs canonical PR head")
    if state.qa_card is None:
        return Decision("DISPATCH", "qa_lead", "DEV validated; independent QA needed")
    if not state.qa_authenticated:
        return Decision("BLOCKED", None, "QA_RESULT review/evidence not authenticated")
    if str(state.qa_card.get("tested_sha", "")).lower() != state.pr_head_sha.lower():
        return Decision("BLOCKED", None, "Stale QA SHA vs PR head")
    verdict = state.qa_card.get("verdict")
    if verdict == "FAIL":
        if state.attempt > state.max_attempts:
            return Decision("BLOCKED", None, "QA rework attempt limit")
        return Decision("DISPATCH", "dev_lead", "Authenticated QA failure; bounded DEV rework")
    if verdict == "PASS":
        if state.pr_merge_authenticated:
            return Decision("HUMAN_GATE_MAP", None, "Merged code verified; map change requires approval")
        return Decision("QA_PASSED_AWAITING_OWNER_MERGE", None, "QA authenticated; no automatic merge")
    return Decision("BLOCKED", None, "Non-PASS/FAIL QA outcome requires human reconciliation")


@dataclass(frozen=True)
class TaskPacket:
    request_id: str
    task_id: str
    project_id: str
    role: str
    target_identity: str
    transport: str
    workspace: str
    canonical_url: str
    canonical_revision: str
    baseline_sha: str
    tested_sha: str | None
    scope: str
    acceptance: tuple[str, ...]
    allowed_paths: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    attempt: int
    stop_conditions: tuple[str, ...] = (
        "unknown target identity", "SHA drift", "ambiguous receipt",
        "unauthorized action", "scope change",
    )
    expected_handoff: str = "DEV_HANDOFF or QA_RESULT referencing the canonical GitHub record"

    def brief(self) -> str:
        """No claim of authority or pass inferred from transport completion."""
        return json.dumps(vars(self), sort_keys=True, ensure_ascii=False)


def make_packet(state: CanonicalSnapshot, target: Target) -> TaskPacket:
    decision = next_action(state)
    if decision.phase != "DISPATCH" or target.role != decision.role:
        raise ValueError("The trusted canonical state does not authorize this target/role")
    if target.project_id != state.project_id:
        raise ValueError("Target is registered for another project")
    if target.role == "dev_lead":
        for path in state.allowed_paths:
            normalized = normalize_repo_path(path)
            if is_protected(normalized):
                raise ValueError("Protected governance path cannot be delegated to normal DEV; use GATE_PR")
    if target.role == "qa_lead" and not state.pr_head_sha:
        raise ValueError("QA requires a fixed candidate SHA")
    payload = "|".join((state.project_id, state.task_id, state.record_url,
                        state.revision, state.pr_head_sha or state.baseline_sha,
                        decision.role, str(state.attempt)))
    request_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return TaskPacket(
        request_id=request_id, task_id=state.task_id, project_id=state.project_id,
        role=target.role, target_identity=target.identity, transport=target.transport,
        workspace=target.workspace, canonical_url=canonical_url(state.record_url),
        canonical_revision=state.revision, baseline_sha=sha(state.baseline_sha),
        tested_sha=sha(state.pr_head_sha) if state.pr_head_sha else None,
        scope=state.scope, acceptance=state.acceptance,
        allowed_paths=state.allowed_paths,
        allowed_actions=tuple(sorted(ALLOWED_ACTIONS[target.role])),
        attempt=state.attempt,
    )
