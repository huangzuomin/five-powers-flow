# Issue #61 · Coordination dispatch minimum-design audit

Status: PROPOSED_IMPLEMENTATION, NOT independent QA, NOT end-to-end certified.

## Verdict on the issue

**Valid P1 capability gap**, not a regression defect in FPF 0.2. The issue accurately
separates GitHub canonical governance, Bootstrap worktrees, and single-slice runtime.
Its requested live Codex/ChatGPT smoke tests cannot be inferred from unit tests.
Treat the broad acceptance checklist as milestones: a safe, testable core first,
real provider-specific adapters and live acceptance second.

## Present interfaces (verified against this repository and this session)

- `packages.fpf_coordinator.coordinator`: validation of structured DEV/QA
  cards, Git ancestry and evidence. DO NOT create an alternate QA PASS authority.
- `packages.fpf_runtime`: one-slice worker, not an externally addressable
  existing Codex Desktop or ChatGPT product thread.
- `packages.fpf_bootstrap`: role prompt files and detached QA worktrees, not
  actual ChatGPT conversation provisioning.
- Connected Codex workspace interface here only exposes workspace **read**
  operations, Git status/diff and execution summaries. No `send-to-thread`
  or `list-threads` contract is exposed.
- Connected browser interface is **read-only** (`list_tabs` /
  `get_tab_context`). It cannot authenticate, send messages, or complete the
  requested browser smoke. An attached browser/bridge provider must implement
  its own authenticated driver separately.

## Scope, integrity and authority

Implement `packages/fpf_coordinator/dispatch/` containing strict packets, an
operator-owned target registry, a transport protocol, bridge/web adapter
facades (driver injection required), a persistent checkpoint/event journal,
and a fail-closed dispatch controller. A canonical-state reducer derives
eligible next role from GitHub records **only after upstream validation**.
`QA_RESULT` text and transport completion are never QA attestation; the
independent GitHub review+artifact verifier remains the sole QA authority.

- GitHub issue/PR URL + immutable baseline/tested SHA pin task identity.
- Requested action scope: DEV editing restricted to explicitly allowed paths;
  QA review is read-only. No transport has merge/deploy/publish permission.
- Explicit human gate for scope authorization, merge, deployment and policy.
- `dispatch()` returns a provider receipt, not task completion.
- `read_status()` consumes provider-reported status and immutable result ref;
  a status is observational, not an independent QA PASS.
- The SQLite journal stores a stable request ID, registered target identity,
  outbound content hash, receipt, attempt, phase, and previous observations.
  Every intent is committed BEFORE any outbound send. Unknown send outcomes
  become BLOCKED_RECONCILIATION, never blind retries.
- Cross-process per-database OS file lock during dispatch or reconciliation.
- No ChatGPT UI session IDs fabricated; no real Codex threads invented.
- Identity registrations are provided by authorized project operator, not
  discovered from untrusted repository text.
- No permanent daemon/scheduler claim in this slice.

## Definition of done and exclusions

Hermetic tests must cover idempotent dispatch, distinct roles and approved
targets, SHA drift, accepted != completed, unknown outcome, restart and
bounded QA rework, plus verified GitHub state transitions. This is **core
contract validation only**.

Live Codex thread send+result+files and ChatGPT authenticated browser
send+visible reply remain NOT_RUN/BLOCKED until a real provider interface,
registered targets, operator authorization, and physical smoke environment
are present. Follow-up work must measure durable cursor, scheduler uptime,
and full external EVID/QA chain before asserting unattended operation.

## Follow-up after external FAIL review

See [COORDINATION-DISPATCH.md](COORDINATION-DISPATCH.md) for the
content-bound GitHub approval event, authenticated physical diff gates, QA
FAIL validation, explicit provider lookup recovery, owner merge gate and
bounded foreground runner. The provider-specific live smoke items remain
NOT_RUN and do not inherit any certification from unit tests.
