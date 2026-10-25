# FPF Bootstrap 0.3 — onboarding a new project

**Status: experimental.** This module is built on FPF Runtime 0.2 (PR #27).
It does not provision existing ChatGPT UI threads, merge code, deploy, create
GitHub PRs, or certify independent QA. Bootstrap is **not** a normal feature slice.

## Lifecycle

UNINITIALIZED -> BOOTSTRAP_PLAN -> BOOTSTRAP_REVIEW ->
(human reviews initial PROJECT-MAP, creates/approves BOOTSTRAP_PR) ->
PROJECT_READY (future gate).

Today the module implements planning, local worktree provisioning, generated
bootstrap documentation and a diagnostic doctor; it never automatically marks
PROJECT_READY. A separate GitHub BOOTSTRAP_PR gate, API session provisioning,
human baseline approval check and PR publication remain follow-up work.

## Install

    python -m pip install -e .

Works with Python >=3.10, Git and Git Worktree on Windows 11. Runtime
API/Agents SDK usage is optional for bootstrap planning.

## Plan first: NO filesystem mutation

    fpf init --repo "C:/Projects/new-app" --workspace-root "C:/FPF/workspaces" --project-id MYAPP01 --title "New App"

The output is a JSON plan listing the baseline SHA, discovered README/docs
headings, proposed branch names, worktree paths and initial files. Only files
tracked by the selected Git commit are inventoried; an uncommitted requirements
draft is never silently taken as the approved baseline. Only README and
bounded markdown/text/rst documentation are indexed in v0.3; PDF/DOCX
extraction and AI synthesis are not yet supported. The initial map is a
**conservative factual skeleton**, not an AI-generated architecture assessment.

You may point at a specific baseline with --base-ref origin/main and change
the documentation directory with --docs-dir docs. No GitHub admin token needed.

## Provision

    fpf init --repo "C:/Projects/new-app" --workspace-root "C:/FPF/workspaces" --project-id MYAPP01 --title "New App" --agent-mode api --apply

Creates three worktrees under the external workspace root:
- bootstrap: fpf/bootstrap-MYAPP01 branch, with initial map and configs;
- dev: fpf/dev-MYAPP01 branch, with a clean fixed baseline;
- qa: detached exact baseline commit.

The bootstrap branch is local only. No change is written to the original
checked-out branch; generated bootstrap files are UNCOMMITTED in its worktree.
Explicit user review, commit, push and a BOOTSTRAP_PR are subsequent steps.
Re-running with identical inputs reuses worktrees and identical files; different
existing content is preserved and initialization fails closed.

Files generated in the bootstrap worktree:
- AGENTS.md
- docs/coordination/PROJECT-MAP.md
- docs/coordination/LESSONS.md
- docs/coordination/HANDOFF-PROTOCOL.md
- .fpf/project.yaml, .fpf/agents.yaml, .fpf/discovery.json
- .fpf/prompts/ for orchestrator, dev_lead, qa_lead and scribe.

All roles have status CONFIGURED_NOT_VERIFIED. The API mode produces agent
definitions suitable for a later Agents SDK provisioning step; it does **not**
claim to have created remote or persisted agent sessions. Choose
--agent-mode manual to additionally generate CHATGPT-SETUP.md with user steps
for manually creating four ChatGPT product conversations.

## Check

    fpf doctor --repo "C:/Projects/new-app" --workspace-root "C:/FPF/workspaces" --project-id MYAPP01

Doctor checks physical worktree provenance, branch/head SHA and artifacts.
A partially configured or unapproved project reports BOOTSTRAP_PARTIAL with
exit code 2; it does not pretend the project is ready. At this stage, user
approval, API provisioning, authentic server-side independent QA requirements,
and the initial BOOTSTRAP_PR gate are explicitly outstanding.

## Model of authority

Bootstrap can propose the **first** map without an existing code PR, but
it cannot perform regular post-merge MAP_UPDATE. The normal FPF dual-PR
policy remains unchanged. In particular, the current CI
validate-handoff-cards workflow rejects mixed governance and config
changes: until the dedicated BOOTSTRAP_PR validator is implemented, the
generated files must NOT be treated as an automatically mergeable PR.

No prior QA_PASS, DEPLOYED, code-complete claim, or real ChatGPT thread ID
is inferred from documentation. Existing target governance files trigger a
hard stop, not overwrite. Session tokens and local workspace paths remain
outside committed project metadata.

## Offline verification

    python -m unittest discover -s tests -p "test_*.py"

New tests exercise dry-run, idempotent worktree provisioning, source repository
integrity, safe refusal to overwrite governance, manual vs API role config,
doctor fail-closed, and workspace path isolation.
