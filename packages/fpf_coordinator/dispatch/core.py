# -*- coding: utf-8 -*-
"""FPF Autonomous Engineering Coordinator Canonical Snapshot & State Reducer Core."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any
from urllib.parse import urlsplit

from .states import Phase, Decision, HUMAN_GATE_PHASES, TERMINAL_PHASES

SHA_RE = re.compile(r"^[a-f0-9]{40}$")
TASK_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
ROLES = frozenset({
    "dev_lead", "dev_worker", "qa_lead", "qa_worker", "scribe", "owner_delegate",
})
ALLOWED_ACTIONS = {
    "dev_lead": frozenset({"plan", "slice", "review_handoff"}),
    "dev_worker": frozenset({"edit_feature_branch", "run_local_tests"}),
    "qa_lead": frozenset({"admission", "freeze_plan", "review_evidence", "sign_qa"}),
    "qa_worker": frozenset({"run_independent_tests", "collect_artifacts"}),
    "scribe": frozenset({"draft_map_pr"}),
    "owner_delegate": frozenset({"orchestrate", "report"}),
}


def validate_sha(value: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value.lower().strip()):
        raise ValueError(f"A pinned 40-hex Git SHA is required, got: {value!r}")
    return value.lower().strip()


def canonical_url(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Canonical GitHub URL required")
    parsed = urlsplit(value)
    bits = parsed.path.strip("/").split("/")
    if (parsed.scheme != "https" or parsed.netloc != "github.com" or
            parsed.query or parsed.fragment or len(bits) != 4 or
            bits[2] not in ("issues", "pull") or not bits[3].isdigit() or
            not all(re.fullmatch(r"[A-Za-z0-9_.-]+", piece)
                    for piece in (bits[0], bits[1]))):
        raise ValueError(f"Expected https://github.com/owner/repo/issues/N or pull/N, got: {value!r}")
    return "https://github.com/" + "/".join(bits)


def make_idempotency_key(task_id: str, attempt: int, canonical_sha: str, action: str) -> str:
    raw = f"{task_id}:{attempt}:{canonical_sha.lower()}:{action}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


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
        if self.role not in ROLES:
            raise ValueError(f"Unknown role: {self.role!r}")
        if self.transport not in ("codex_thread", "codex_cli", "chatgpt_web", "claude_web"):
            raise ValueError(f"Unknown transport: {self.transport!r}")
        if not TASK_ID_RE.fullmatch(self.project_id):
            raise ValueError(f"Invalid project ID: {self.project_id!r}")


@dataclass(frozen=True)
class CanonicalSnapshot:
    task_id: str
    project_id: str
    record_url: str
    revision: str
    baseline_sha: str
    pr_head_sha: str | None = None
    scope: str = ""
    allowed_paths: tuple[str, ...] = field(default_factory=tuple)
    forbidden_paths: tuple[str, ...] = field(default_factory=tuple)
    scope_authorized: bool = False
    work_order: dict | None = None
    qa_admission: dict | None = None
    dev_card: dict | None = None
    dev_validated: bool = False
    qa_plan: dict | None = None
    qa_card: dict | None = None
    qa_authenticated: bool = False
    pr_merged: bool = False
    code_merged_sha: str | None = None
    map_card: dict | None = None
    map_pr_merged: bool = False
    attempt: int = 1
    max_attempts: int = 3
    last_failure: str = ""

    def __post_init__(self) -> None:
        if not TASK_ID_RE.fullmatch(self.task_id):
            raise ValueError(f"Invalid task_id: {self.task_id!r}")
        if not TASK_ID_RE.fullmatch(self.project_id):
            raise ValueError(f"Invalid project_id: {self.project_id!r}")
        canonical_url(self.record_url)
        validate_sha(self.baseline_sha)
        if self.pr_head_sha is not None:
            validate_sha(self.pr_head_sha)
        if self.code_merged_sha is not None:
            validate_sha(self.code_merged_sha)
        if not (1 <= self.attempt <= self.max_attempts <= 10):
            raise ValueError(f"Invalid attempt policy: attempt={self.attempt}, max={self.max_attempts}")
        for p in self.allowed_paths:
            if not isinstance(p, str) or not p.strip() or p.startswith("/") or ".." in p.replace("\\", "/").split("/"):
                raise ValueError(f"Invalid allowed path: {p!r}")


@dataclass(frozen=True)
class TaskPacket:
    request_id: str
    idempotency_key: str
    task_id: str
    project_id: str
    role: str
    target_identity: str
    transport: str
    workspace: str
    baseline_sha: str
    tested_sha: str | None
    scope: str
    allowed_paths: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    attempt: int
    max_attempts: int

    def brief(self) -> str:
        return json.dumps({
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "task_id": self.task_id,
            "project_id": self.project_id,
            "role": self.role,
            "target_identity": self.target_identity,
            "transport": self.transport,
            "baseline_sha": self.baseline_sha,
            "tested_sha": self.tested_sha,
            "scope": self.scope,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
        }, sort_keys=True, ensure_ascii=False)


def next_action(state: CanonicalSnapshot) -> Decision:
    """Pure, deterministic state reducer over canonical snapshot.

    Never relies on natural language. Evaluates strict preconditions in accordance
    with the FPF-AEC 24-state transition table.
    """
    # 1. 范围授权前置门 (Human Scope Authorization Gate)
    if not state.scope_authorized:
        return Decision(
            phase=Phase.HUMAN_SCOPE_AUTHORIZATION_PENDING,
            role=None,
            reason="Scope authorization required from human sovereign",
            requires_human=True,
        )

    # 2. DEV 工作令检查 (WORK_ORDER)
    if not state.work_order:
        return Decision(
            phase=Phase.DEV_DESIGN_PENDING,
            role="dev_lead",
            reason="Missing WORK_ORDER; DEV design required",
        )

    # 3. QA 前置准入门 (QA Admission Gate)
    if not state.qa_admission:
        return Decision(
            phase=Phase.QA_ADMISSION_PENDING,
            role="qa_lead",
            reason="Pre-flight QA Admission review required",
        )

    admission_verdict = str(state.qa_admission.get("verdict", "")).upper()
    if admission_verdict != "ADMITTED":
        return Decision(
            phase=Phase.BLOCKED_ADMISSION_REJECTED,
            role=None,
            reason=f"QA Admission rejected with verdict: {admission_verdict}",
        )

    # 4. DEV 交付卡检查 (DEV_HANDOFF)
    dev = state.dev_card
    if dev is None:
        return Decision(
            phase=Phase.DEV_DISPATCH_PENDING,
            role="dev_worker",
            reason="QA admitted; ready for Codex DEV dispatch",
        )

    # 5. 可信 DEV 校验 (Trusted DEV Validation)
    if not state.dev_validated:
        if state.attempt >= state.max_attempts:
            return Decision(
                phase=Phase.BLOCKED,
                role=None,
                reason="DEV handoff validation failed and max attempts reached",
            )
        return Decision(
            phase=Phase.BOUNDED_DEV_REWORK,
            role="dev_worker",
            reason="DEV handoff validation failed; bounded rework required",
        )

    dev_tested_sha = str(dev.get("tested_code_sha", "")).lower()
    if state.pr_head_sha and dev_tested_sha != state.pr_head_sha.lower():
        return Decision(
            phase=Phase.BLOCKED,
            role=None,
            reason="DEV tested SHA drift vs PR head SHA",
        )

    # 6. QA 方案冻结 (QA Plan Freezing)
    if not state.qa_plan:
        return Decision(
            phase=Phase.QA_PLAN_FREEZE_PENDING,
            role="qa_lead",
            reason="DEV validated; freeze QA Plan on tested SHA",
        )

    plan_target_sha = str(state.qa_plan.get("target_head_sha", "")).lower()
    if plan_target_sha != dev_tested_sha:
        return Decision(
            phase=Phase.BLOCKED,
            role=None,
            reason="QA Plan target_head_sha mismatch vs DEV tested SHA",
        )

    # 7. QA 裁决卡检查 (QA_RESULT)
    qa = state.qa_card
    if qa is None:
        return Decision(
            phase=Phase.QA_DISPATCH_PENDING,
            role="qa_worker",
            reason="QA Plan frozen; ready for Codex QA dispatch",
        )

    # 8. 可信 QA 校验 (Trusted QA Validation)
    if not state.qa_authenticated:
        return Decision(
            phase=Phase.BLOCKED_QA_IDENTITY_UNAVAILABLE,
            role=None,
            reason="QA_RESULT review/evidence not authenticated by independent identity",
        )

    qa_tested_sha = str(qa.get("tested_sha", "")).lower()
    if qa_tested_sha != dev_tested_sha:
        return Decision(
            phase=Phase.BLOCKED,
            role=None,
            reason="QA tested SHA mismatch vs DEV tested SHA",
        )

    verdict = str(qa.get("verdict", "")).upper()
    if verdict == "FAIL":
        if state.attempt >= state.max_attempts:
            return Decision(
                phase=Phase.BLOCKED,
                role=None,
                reason="QA verdict FAIL and max attempts reached",
            )
        return Decision(
            phase=Phase.BOUNDED_DEV_REWORK,
            role="dev_worker",
            reason="QA verdict FAIL; bounded rework required",
        )

    if verdict != "PASS":
        return Decision(
            phase=Phase.BLOCKED,
            role=None,
            reason=f"Non-PASS/FAIL QA outcome requires reconciliation: {verdict}",
        )

    # 9. 代码主干合并门 (Human Code Merge Gate)
    if not state.pr_merged:
        return Decision(
            phase=Phase.HUMAN_GATE_MERGE,
            role=None,
            reason="QA PASS verified; awaiting human code merge approval",
            requires_human=True,
        )

    # 10. 合并可达性校验 (Merge Verification)
    if not state.code_merged_sha:
        return Decision(
            phase=Phase.MERGE_VERIFICATION,
            role=None,
            reason="Code merged but merge commit SHA not verified",
        )

    # 11. Scribe 地图记账 (Scribe Dispatch)
    if not state.map_card:
        return Decision(
            phase=Phase.SCRIBE_DISPATCH_PENDING,
            role="scribe",
            reason="Code merged into main; Scribe map update PR needed",
        )

    # 12. 地图 PR 合并门 (Human Map Merge Gate)
    if not state.map_pr_merged:
        return Decision(
            phase=Phase.HUMAN_GATE_MAP_MERGE,
            role=None,
            reason="Map PR submitted; awaiting human map merge approval",
            requires_human=True,
        )

    # 13. 交付收口与关闭 (Closeout & Closed)
    return Decision(
        phase=Phase.CLOSED,
        role=None,
        reason="Full dual-merge closeout completed and verified",
    )


def make_packet(state: CanonicalSnapshot, target: Target, request_id: str, action: str) -> TaskPacket:
    decision = next_action(state)
    if decision.requires_human:
        raise ValueError(f"Cannot dispatch during human gate phase: {decision.phase.value}")
    if target.role != decision.role:
        raise ValueError(f"Target role {target.role!r} does not match decision role {decision.role!r}")

    tested_sha = None
    if state.dev_card:
        tested_sha = str(state.dev_card.get("tested_code_sha", "")).lower()

    idempotency_key = make_idempotency_key(
        task_id=state.task_id,
        attempt=state.attempt,
        canonical_sha=tested_sha or state.baseline_sha,
        action=action,
    )

    allowed_actions = tuple(sorted(ALLOWED_ACTIONS.get(target.role, set())))

    return TaskPacket(
        request_id=request_id,
        idempotency_key=idempotency_key,
        task_id=state.task_id,
        project_id=state.project_id,
        role=target.role,
        target_identity=target.identity,
        transport=target.transport,
        workspace=target.workspace,
        baseline_sha=state.baseline_sha,
        tested_sha=tested_sha,
        scope=state.scope,
        allowed_paths=state.allowed_paths,
        allowed_actions=allowed_actions,
        attempt=state.attempt,
        max_attempts=state.max_attempts,
    )
