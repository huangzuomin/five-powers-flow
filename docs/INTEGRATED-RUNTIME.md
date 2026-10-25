# FPF Integrated Single-Slice Runtime 0.2

Status: **experimental integration, draft PR only**. No remote merge, deployment, or editing PROJECT-MAP.md.

## Architectural choice / provenance

Reused actual published components:
- OpenAI Agents SDK (optional pip extra) supplies DEV and QA role agents,
  SQLiteSession per role, and Runner.run_sync. These are **new API sessions**,
  not ChatGPT UI threads; SDK conversation state is separate from FPF ledger.
- Official Codex CLI supplies non-interactive codex exec in DEV workspace-write
  and QA read-only sandboxes, with subprocess exit status.
- Git CLI supplies a fixed-SHA detached independent QA worktree.
- GitHub CLI (gh) optionally publishes a **draft** code PR with a machine-generated
  DEV_HANDOFF card. Never auto-merges, auto-deploys, or edits project-map.
- Existing FPF coordinator/schema/CI remains the authority for CODE PR shape.

Upstream Cezar (MIT) and Chipping Orchestrator (Apache-2.0) were inspected
for their workflow/rework/PR design; **neither codebase is vendored or runtime
called**. Two complete orchestrators would duplicate state and introduce
incompatible lifecycle assumptions; Chipping currently targets Linux. Symphony
is architecture inspiration only. Do not claim these engines are integrated.

## Install on Python >=3.10, including Windows 11

Use a disposable, trusted workspace and separate DEV and QA checkout paths.
Install in the FPF checkout with:

    python -m pip install -e ".[agents]"

Prerequisites: Git, Codex CLI authenticated for local noninteractive exec,
OPENAI_API_KEY for OpenAI Agents SDK. To publish a PR, additionally install
GitHub CLI gh, authenticate it to a repository with permission to push a feature
branch and open PRs, and configure origin.

In the **target application repository**, create a clean dedicated feature branch,
not main/master:

    git switch -c feat/fpf-slice-demo

Use absolute paths for Windows, such as C:/work/application and C:/work/qa-slice,
and keep both state DB and evidence outside either worktree.

Example from the FPF checkout, written as a single command to work in PowerShell:

    python -m packages.fpf_runtime.cli --task-id SLICE_DEMO --goal "Implement an isolated health endpoint with tests" --dev-repo "C:/work/application" --qa-worktree "C:/work/qa-slice" --state-db "C:/work/fpf-state/slices.sqlite3" --model YOUR_AVAILABLE_MODEL --dev-check "python -B -m unittest discover -s tests" --qa-check "python -B -m unittest discover -s tests" --max-attempts 3

By default the runtime **does not push or open a PR**. Pass --publish-pr
to explicitly authorize a push of the feature branch and a GitHub draft PR,
and optionally --base-branch main. The output contains the PR URL and the
FPF ledger report. If you require the older simple Responses API integration
rather than the Agents SDK, pass --role-backend responses.

State inspection needs no model or workspace arguments:

    python -m packages.fpf_runtime.cli --task-id SLICE_DEMO --state-db "C:/work/fpf-state/slices.sqlite3" --status-only

## Executed state flow

NEW -> PLAN_RUNNING -> PLANNED -> DEV_RUNNING -> DEV_READY -> QA_RUNNING
-> (NEEDS_REWORK -> DEV again) OR (QA_PASSED_LOCAL -> PUBLISH_RUNNING)
-> READY_FOR_OWNER_REVIEW.

When --publish-pr is absent, QA success directly results in READY_FOR_OWNER_REVIEW
without any GitHub changes.

Each QA attempt checks the exact tested SHA in a detached worktree. Codex review
returns a JSON finding; an **independently launched deterministic QA command**
must also return exit 0. A local manifest stores reviewer output, check command,
exit code and checksums of two evidence files. Evidence is bound to the tested
SHA and kept outside both worktrees. When an artifact is stale/tampered, PR
publication refuses to proceed. This is **provisional local QA evidence** and
not independent GitHub CI-verified proof.

Failed checks trigger bounded development attempts, with error messages passed
to the next DEV agent plan. Agent failures with uncertain side effects, interrupted
external calls and interrupted GitHub publication stop at
BLOCKED_RECONCILIATION. The runtime does not blindly re-execute commands after
a process crash. SQLite stores task state and an append-only event record.

## Trust and operational constraints

1. QA and DEV worktrees are distinct, but **share the host OS account and Git
   common-dir**: this is workspace isolation, NOT OS credential isolation.
   Run in a disposable VM/container with least-privilege credentials.
2. GitHub write tokens are removed from Codex/test subprocess environment, but
   this is not a sufficient sandbox for untrusted PR code. Use separate OS users
   or hosted runners to enforce independent principal and filesystem boundaries.
3. The existing GitHub CI can still accept a CODE PR with no mandatory verified
   QA check. The generated PR therefore stays a draft awaiting owner review.
4. FPF's current QA_RESULT schema and profile evidence are **not** claimed satisfied
   by this lightweight local QA manifest. A future CI workflow must generate and
   validate its own evidence against a remote, immutable PR-head commit.
5. This branch has hermetic tests, not verified live Codex/API/GitHub credentials;
   Win11 direct integration remains a separate acceptance requirement.
6. Attempts and max-steps are bounded. External models can still consume tokens;
   there is no unified monetary budget circuit breaker in v0.2.

## Local smoke/CI

    python -m unittest discover -s tests -p "test_*.py"

Important negative tests: stale SHA, modified QA log, deterministic check FAIL
even when model says PASS, interrupted publication not retried, optional publisher
disabled by default, and role SDK SQLite conversations remain separate.

## Future production hardening

Required QA GitHub status check scoped to exact head SHA, credential-separated QA,
external process IDs/restart reconciliation, budget enforcement, PR confirmation,
durable artifact store and a negative smoke test on the user's actual Windows
Codex version. These have not been claimed complete.
