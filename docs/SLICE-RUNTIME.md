# FPF Runtime 0.1 — unattended handoff within one feature slice

**Experimental reference implementation.** It does not push to GitHub, merge PRs, deploy,
update the official project map, or claim server-enforced independent QA.

## Scope

One invocation:
Human goal -> ChatGPT API DEV role -> Codex DEV feature worktree -> deterministic
DEV check -> ChatGPT API QA role -> detached QA worktree -> read-only Codex QA
review -> deterministic QA command -> FAIL/rework loop or READY_FOR_OWNER_REVIEW.

The ChatGPT roles are **new API-backed Responses sessions**, with role-specific
previous_response_id stored in SQLite. **Existing ChatGPT product UI threads are
not programmatically resumed.** The Codex adapter uses the CLI, not an existing
Codex Desktop thread. These distinctions matter for the requested workflow.

## Requirements

- Python 3.10+, Git, an installed Codex CLI, API model access, OPENAI_API_KEY.
- A clean target repository on a **dedicated feature branch**, not main/master.
- A separate QA worktree path **outside** the DEV repo and a SQLite path
  outside both worktrees.
- Two explicitly configured verification commands, chosen for the target repo.
  The commands are executed with subprocess without a shell.
- A disposable, least-privilege local environment. The orchestration process
  makes local Git commits, but never pushes or merges. Credentials should not
  be available to untrusted code.

## Example command

    git switch -c feat/slice001
    python -m packages.fpf_runtime.cli \
      --task-id SLICE001 \
      --goal "Implement a health endpoint with tests" \
      --dev-repo /path/to/target-project \
      --qa-worktree /path/to/isolated/qa-slice001 \
      --state-db /path/to/fpf-state/slices.sqlite3 \
      --model YOUR_RESPONSES_MODEL \
      --dev-check "python -B -m unittest discover -s tests" \
      --qa-check "python -B -m unittest discover -s tests" \
      --max-attempts 3

Use Windows or POSIX paths appropriate to the host. The installed Codex CLI
must support non-interactive exec, sandbox and output-last-message options.
The CLI version has not been validated against the user's Windows installation.

To inspect saved progress, use the same CLI arguments and --status-only,
ensuring --state-db points at the previous run.

## Trust and recovery guarantees

A final PASS requires both the independent QA review to return strict JSON PASS
and a separate QA process to exit 0. The isolated QA checkout must match the
exact DEV SHA and remain clean. QA failures generate a new DEV work order and
retry, bounded by max-attempts and max-steps. Role response IDs and state
transitions are persisted in SQLite.

An interrupted in-flight API or Codex operation cannot be retried safely without
external execution IDs. This prototype therefore enters BLOCKED_RECONCILIATION
instead of automatically replaying an uncertain command.

A QA model may return inaccurate judgments; the deterministic QA command is
the independent executable assertion. Local heuristic secret scans and SHA
checks are **not** an authentication or security boundary equivalent to
remote required status checks.

## Gaps deliberately not implemented in 0.1

1. Publishing the resulting local commit to a GitHub PR with exact head SHA.
2. Authenticated GitHub QA required check and an immutable CI evidence bundle.
3. Verifying QA authorship against a separate principal (never trust an author string).
4. Durable process IDs and in-flight restart reconciliation; cost budgets and kill switch.
5. Actual external-service Windows Codex and Responses API integration testing.

## Tests

    python -m unittest discover -s tests -p "test_*.py"

New hermetic tests simulate a successful slice, independent QA FAIL -> bounded
DEV rework -> QA PASS, Codex work without Git commit permission, preserved main,
dirty/unrelated QA directory protection, and an interrupted-run fail-closed path.
They do not make live OpenAI, Codex, or GitHub calls.
