# Fifth independent audit — disposition of GitHub Issues #29–#45

Scope: FPF main 1637c090, remediation PR #46. This is a technical
implementation ledger, **not** an independently signed QA_PASS. GitHub status
checks, physical artifacts and human approvals must be observed separately.

## Issue-by-issue trace

| Issue | Disposition in PR #46 | Remaining acceptance condition |
|---|---|---|
| #29 (overall review) | Tracked here; no independent QA claim | External auditor rechecks every descendant |
| #30 P0 fake sample artifacts | Deleted placeholder logs, manifest and fake cards; replaced with explicit prose-only example | Confirm deleted blobs inaccessible from HEAD, no historic SHA reuse |
| #31 P0 QA card disconnected | Separate platform-authenticated APPROVED Review on latest SHA, trusted Actions run + manifest and checks in required validate-card | Second real reviewer must demonstrate successful run |
| #32 P0 CODEOWNERS zero approvals | CI explicitly rejects absence of distinct reviewer; CODEOWNERS widened | Admin config needs required_approving_review_count >= 1, not possible from current GitHub App |
| #33 P0 bootstrap contaminated PR | Classified narrow BOOTSTRAP_PR with independent approval; bootstrap ships validator workflows/hooks/schemas | Genuine target repo bootstrap PR and owner approval required |
| #34 P0 NOT_APPLICABLE bypass | Mandatory items must have real verified SHA; duplicate or N/A blocked | Independent runner trials |
| #35 P1 not_run self-exemption | Empty not_run and old exemption field forbidden | Tests for valid real coverage matrix future |
| #36 P1 profile downgrade | Accepted documented exact aliases, unknown/mismatch fail closed | Profile syntax tests on CI |
| #37 P1 mandatory evidence too few | Full-Stack 28 applicable items including EVID-21–24, API-DB 24; Rework requires red-green G; docs corrected | Rich full-stack and API environment proof must be tested in project |
| #38 P1 self-declared identities | Author required, matched to authenticated PR and approved review actors | Independent reviewer/principal required |
| #39 P1 QA runner pinned to tested code | PASS rejects runner/contract equal tested, enforces pre-DEV ancestry; trusted main QA workflow | Separate QA repository refs not yet supported |
| #40 P1 runtime evidence incompatible | Added EVID full-manifest bridge; no filling missing items | Real QA command plan and authenticated artifacts |
| #41 P1 in-PR evidence | CI no longer reads PR-owned docs/evidence; verifies trusted-main workflow run and GitHub artifact by ID | CI permission and real runner demonstration |
| #42 P2 bootstrap doctor/rollback/mechanism | doctor --check, PENDING journal, safe rollback, vendor CI/hooks/schema templates | Agent session provisioning, automated BOOTSTRAP_PR publication, human-approved READY reconciliation missing |
| #43 P2 inconsistent paths and traversal | Central protected-path module, all local DEV checks use it; fixed path containment, policy-change PR lane | Cross-platform adversarial shell coverage not exhaustive |
| #44 P2 contradictory docs | Removed changelog duplicate; README module index; calibrated claims; corrected QA review location and profiles | Independent content audit |
| #45 P2 merge assertion | No repo ancestry => MERGE_UNVERIFIED, never cryptographic success based on flag | For true squash merges, `--verify-pr-merge` queries authenticated GitHub PR state, binds headRefOid to QA-tested SHA, and verifies mergeCommit ancestor in main (unit-tested) |

## Reviewer prerequisites

1. A **second distinct GitHub principal** is required for APPROVED reviews.
   Change branch protection settings to require >=1 approval and code-owner
   approval by a real existing independent owner. This GitHub connector does
   not provide supported repository administration actions.
2. Promote an **independently approved, project-specific** ".fpf/qa-plan.json"
   to protected main before dispatching "FPF Independent QA" on a candidate SHA.
   The plan is a mapping of required EVID-ID to real argv test commands;
   a string "PASS" or dummy log is not acceptable. Collector will refuse a
   missing command, a failing command or a SHA mismatch.
3. Reviewer dispatches workflow_dispatch from trusted main, then embeds the
   resulting run/artifact IDs, current tested SHA and printed true manifest
   SHA256 into a QA_RESULT inside a GitHub APPROVED PR Review. The same actor
   must own the QA run and the approving review. Any later PR push expires it.
4. For protected POLICY_PR / MAP_PR / BOOTSTRAP_PR, independent review of the
   exact current HEAD is mandatory; CODE_PR also needs the separately
   authenticated actual QA evidence. No exception for a single-collaborator
   repository, even if it means remaining unmergeable.
5. QA artifacts are stored via GitHub Actions, not committed by DEV. To get
   useful EVID-22 browser screenshots, or API/database traces, the reviewer
   must implement real test commands in the trusted plan, not echo descriptions.
6. Tests prove boundary behavior on CI, not cross-vendor model correctness or
   runtime isolation across OS users. Windows deployment and true application
   E2E remain explicit separate acceptance criteria.

This audit retains Issues #29–#45 open until independent QA confirms their
remediation; a merged PR cannot retroactively authenticate earlier samples.
