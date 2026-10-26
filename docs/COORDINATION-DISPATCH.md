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


## Reviewer remediation: authorization, diff, QA and recovery

- A GitHub issue creator is **not** an authorization. The currently configured
  approver must have live GitHub admin/maintain/write permission and post a
  GitHub-authenticated FPF_SCOPE_GRANT event. A platform-authenticated comment
  is **not a cryptographic signature**. The grant binds the exact Issue body
  SHA-256, issue.updated_at, baseline SHA, project ID, task ID, target branch,
  and max_attempts. Only the most recent relevant grant/revocation by the
  configured approver is considered. Edits/revocation/permission loss block.
- Issue comment (GitHub markdown fenced YAML) must include these fields:

      kind: FPF_SCOPE_GRANT
      grant_version: 1
      issue_url: https://github.com/OWNER/REPO/issues/NUMBER
      task_id: APPROVED_TASK_ID
      project_id: APPROVED_PROJECT_ID
      issue_revision: ISSUE_UPDATED_AT_FROM_API
      work_order_sha256: 64_HEX_SHA256_OF_EXACT_ISSUE_BODY
      baseline_sha: 40_HEX_APPROVED_BASE_COMMIT
      target_branch: APPROVED_FEATURE_BRANCH
      max_attempts: 2

  To revoke, the same still-authorized principal submits a separate comment
  with kind FPF_SCOPE_REVOKE and the same issue_url. An Issue edit requires a
  fresh grant; an expired or different project/branch grant never authorizes.
- Before QA dispatch, the actual Git diff is read from fixed Git commit
  objects; every changed path must match an explicitly allowed file or
  directory prefix (end a prefix with a slash). A DEV_HANDOFF listing a
  rogue file accurately is still blocked. PR base.sha and head.ref must
  match the approved baseline and target_branch. There is no alternate
  caller-supplied baseline bypass.
- Neither QA PASS nor QA FAIL is authenticated by review prose alone.
  Both require a complete QA_RESULT with findings, next_action, original
  evidence directory, trusted Coordinator validation, and an injected
  independent GitHub review/Actions artifact authenticator. A four-field
  CHANGES_REQUESTED is not a signed QA failure.
- DispatchJournal freezes the per-task grant ID, approved scope, baseline
  and retry ceiling. canonical_attempt derives repeat/rework attempts from
  durable DEV requests and authenticated fixed-SHA FAIL; reverting the
  caller argument cannot increase allowance. A new authorization/scope
  requires a new task ID.
- Explicit Coordinator.reconcile(request_id) can recover an interrupted
  SENDING state by a provider-side unique lookup keyed to request ID and
  registered target, **without sending a second message**. Providers
  without unique lookup leave BLOCKED_RECONCILIATION.
- A merged PR only reaches HUMAN_GATE_MAP if GitHub supplies merged state,
  merged_at and merge_commit SHA, the merge commit is physically present
  on the inspected default-branch history, and external QA PASS is verified.
- CoordinationRunner.tick/run_bounded implement a finite foreground
  observe→re-read-GitHub→dispatch-next loop. Transport completion by
  itself never produces DEV_READY or QA_PASS. This is not a scheduled
  daemon or a live ChatGPT/Codex integration.

## Still NOT_RUN

Real Codex thread bridge, authenticated ChatGPT Web send/read smoke, hosted
scheduler and cursor under real OS crashes, Windows 11 lock/restart
verification, trusted external reviewer QA artifact, and physical end-to-end
DEV→QA→FAIL→rework→PASS flow. Their absence keeps Issue #61 open and PR #62
as Draft, even while offline tests pass.
