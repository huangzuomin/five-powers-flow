# FPF Issue #61 — role dispatch core

Status: EXPERIMENTAL. Does not claim live Codex/ChatGPT transport or independent QA PASS.

## Boundaries

- GitHub Issue/PR records remain the canonical task source. from_github_records validates WORK_ORDER and binds DEV_HANDOFF to a real Git checkout and authenticated PR author.
- QA PASS remains blocked unless an external trusted review+artifact verifier is provided. Local transport completion never signs QA.
- Target registrations require an explicit project, role, thread/conversation identity, workspace, and approved flag. Registry must be provisioned by the human project owner.
- RoleTransport is a Python driver contract. CodexThreadBridge requires send_thread_message/thread_status/cancel_thread_turn. ChatGPTWebTransport requires send_visible_message/read_visible_reply on a registered, authenticated conversation.
- This connected environment has only read-only Codex workspace and browser interfaces, not live writable thread/browser drivers. Do not invent thread IDs or bypass login.
- Controller persists a request intent BEFORE send, the returned receipt, observations and bounded polling in SQLite. Unknown send status or interrupted dispatch blocks reconciliation, never blind retry.
- OS file locking prevents simultaneous dispatch by two local coordinator invocations. This is not a hosted always-on scheduler.
- DEV and QA are independent roles. Merge, publish, deploy, and QA signing are never allowed transport actions.

## Usage with a real registered driver

An application supplies a trusted canonical snapshot and a registered target. It constructs DispatchJournal(Path(...)), Coordinator(journal, registry, transports), then calls dispatch_next(snapshot) and observe(request_id). ACKNOWLEDGED is receipt only; TRANSPORT_COMPLETED_UNVERIFIED is not QA_PASS. A new verified GitHub snapshot is required for the next role.

## Validation still outstanding

Core hermetic tests do not count as physical independent QA. Real Codex thread bridge dispatch/status/actual file evidence, authenticated ChatGPT browser send/visible reply, GitHub approved-review and Actions artifact binding, real Windows restart smoke, and scheduler/daemon durable cursor are NOT_RUN. No human merge/deployment authorization is inferred.

See docs/ISSUE-61-DESIGN-AUDIT.md for the pre-implementation design review.

Read-only GitHub entry: GitHubReadOnlySource('owner/repo').snapshot(...) reads
Issue, PR, and paginated Reviews through gh api. The Issue author must match
an explicitly configured approved_owner_login; scope changes or approvals
from other authorized principals require a separate signed grant mechanism.
Do not grant GitHub API tokens to DEV worktree code or web driver scripts.
