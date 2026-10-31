# Changelog

All notable changes to the **Five-Powers-Flow (FPF)** project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Fixed `SliceRuntime` type subtraction defect (`TypeError: unsupported operand type(s) for -: 'list' and 'set'`) in `packages/fpf_runtime/runtime.py`.
- Upgraded `.fpf/qa-plan.json` and `templates/qa-plan.example.json` commands from placeholder print outputs to real AST parsing, bytecode compilation, and file assertions (R4 remediation).
- Fixed GitHub Actions QA artifact download in `packages/fpf_policy/qa_artifact.py` by stripping `Authorization` bearer headers on pre-signed S3 redirects (`_NoAuthRedirectHandler`).
- Enhanced QA workflow provenance verification to inspect `origin/{base_ref}` and `refs/remotes/origin/{base_ref}` in addition to local base references.

### Added
- Added Five-Powers-Flow Standard Operational Guide in `docs/OPERATIONAL-GUIDE.md`.
- Added OMAP Real-Project Rehearsal Third-Party Independent Audit Report in `docs/AUDIT-OMAP-REHEARSAL.md`.
- Added regression unit test `test_qa_evidence_dir_export_manifest` in `tests/test_slice_runtime.py`.
- Added `--allow-existing-governance` flag to `fpf init` (`packages/fpf_bootstrap`) to onboard repositories with existing baseline governance files without collision or unintended overwrites.
- Added unit tests in `tests/test_project_bootstrap.py` covering existing governance preservation.
- Hardened repository exclusion hygiene to prevent local ad-hoc rehearsal scripts and session rollout archives from polluting open-source tracking; expanded POLICY_CHANGE scope in `packages/fpf_policy/pr_gate.py` to recognize root repository configuration files.

### Fixed (Audit round five — pending independent QA)
- Reject placeholder evidence, self-attested test exemptions, unsigned authorship strings as proof, and unknown evidence profiles.
- Added a shared protected-path policy and negative audit regression tests.
- Added fail-closed project onboarding, GitHub platform reviewer checks, and protected-main Actions artifact provenance checks; native reviewer count remains separately administered.
- Added a reference independently dispatched QA runner; projects must configure authentic reviewed test commands before any trusted PASS.


## [1.2.1] - 2026-10-25

### Added
- **Restoration of Specification Body (§4–§7) (Issue #18)**: Fully restored and hardened §4 Standard Hand-off Contracts (`DEV_HANDOFF`, `QA_RESULT`, `MAP_UPDATE`), §5 Physical Isolation Rules, §6 Quality Gates & Red Check, §7 Dual-PR Ordering & Anti-Drift Workflow in `docs/SPECIFICATION.md`.
- **PreToolUse Hook Guard Expansion & Bash Interception (Issue #17)**: `packages/fpf_gates/hook_guard_dev.py` now protects both `PROJECT-MAP.md` and `LESSONS.md`, and intercepts common mutation commands in `Bash` (`>`, `>>`, `tee`, `sed -i`, `cp`, `git checkout`). Added in-tree configuration `.claude/settings.json`.
- **Evidence Manifest Schema & Directory (Issue #19, #20, #21)**: Added `schemas/manifest.schema.json` with formal Draft-07 schema for 32 evidence items and Profiles; established canonical reference evidence directory `docs/evidence/` with sample manifest, logs, and cards.
- **Dual-PR Workflow Routing (P0-01, P0-02)**: Dedicated CI workflow separation for `MAP_PR` vs `CODE_PR`. Code PRs are strictly rejected if missing `DEV_HANDOFF` card or touching governance files; Map PRs are anchored to merged Code commit ancestors (`code_merged_sha`).
- **PR Head SHA Binding (P1-01)**: Server-side CI validates that `DEV_HANDOFF.tested_code_sha` strictly matches `github.event.pull_request.head.sha`.
- **QA Fact-Based Verdict Enforcement (P0-03)**:
  - QA `verdict: PASS` strictly requires all executed checks to have `exit_code: 0`.
  - QA `verdict: PASS` strictly requires a physical evidence directory (`--evidence-dir`).
  - Evidence Profile enforcement: `manifest.json` cannot have empty `items` and must provide all mandatory items for the declared Profile (`Library`, `API-DB`, `Full-Stack`, `Rework`).
- **Fail-Closed State Machine & Merge Ancestry (P0-04)**: `compute_lifecycle_state` enforces that any DEV/QA errors prevent `MERGED_AND_CLOSED`, and merge closure requires Git ancestry when repository evidence is supplied.
- **Branch Protection Required Status Checks (P0-05, Issue #14)**: Configured GitHub `required_status_checks` on `main` branch enforcing `validate` and `validate-card` jobs with `enforce_admins: true` and `require_code_owner_reviews: true`.
- **Hermetic Boundary Tests (P2-04)**: Expanded boundary-test coverage (historical count; see CI for current count) covering exit codes, profile items, manifest emptiness, hermetic merge ancestry, and NOT_APPLICABLE status reasoning.

### Changed
- **Package Tree Consolidation (Issue #22)**: Completely removed redundant `packages/fpf-coordinator` directory; unified canonical package under `packages.fpf_coordinator`; added CI duplicate module tree check.
- **`not_run` Exemption Matrix (P2-01)**: Permitted empty `not_run` only when accompanied by explicit `not_run_exemption_justification` (min 15 chars) citing test matrix / scope proof.
- **Pre-Handoff Gate 4 Scan Scope (P1-05)**: Changed secret scan from `HEAD~1...HEAD` to full branch diff `merge-base(base, HEAD)..HEAD`.
- **Tone Calibration (P2-03)**: Replaced absolute claims of "不可篡改" with "高可信、防篡改校验与密码学存证机制", accurately reflecting the RFC reference status.

## [1.2.0] - 2026-10-25

### Added
- **Automated PR Body Extraction**: `coordinator.py` supports `--dev-text` and `--qa-text` using active `extract_yaml_block()`.
- **Ancestor & Scope Verification**: `validate_dev_handoff` checks that `baseline_sha` is an ancestor of `tested_code_sha` via `git merge-base --is-ancestor`, and verifies that all actual diff files are declared in `changed_files`.
- **Toolchain Integrity Checks**: `runner_sha` and `qa_contract_sha` are now required in `qa-result.schema.json` and physically checked as valid git commit objects.
- **Physical Evidence Directory Auditing**: `coordinator.py --evidence-dir` reads `manifest.json`, recomputes its SHA-256 against `evidence_manifest_sha256`, and audits all individual evidence files.
- **Server-Side CI Enforcement**: Added `.github/workflows/validate-handoff-cards.yml` to extract and cryptographically validate `DEV_HANDOFF` cards on pull requests.
- **Server-Side Ownership**: Added `.github/CODEOWNERS` for protected governance documents.
- **Formal Python Package**: Added `pyproject.toml` and test suite `tests/test_trusted_evaluator.py`.

### Changed
- **Removed Self-Signed Bypass**: Completely removed `full_coverage_certified` from `coordinator.py` and schema; `not_run` must strictly contain at least 1 declared boundary.
- **Claude Code Hook Protocol**: Updated `docs/CLAUDE-CODE-GUIDE.md` to official `PreToolUse` matcher/hooks array format with standard exit code `2`.
- **Evidence Profile Tiers**: Added 4 profiles (`Library`, `API-DB`, `Full-Stack`, `Rework`) in `docs/EVIDENCE-SPEC.md`.

### Fixed
- Fixed `git_commit_exists` using `git cat-file -t` to enforce object type strictly equal to `commit`.
- Fixed `pre_handoff.py` `gate_3` to fail-closed on git errors and use exact path sets.
- Fixed `pre-push.template` using explicit `git merge-base` to prevent 3-dot diff drift.

## [1.1.0] - 2026-10-24
- Added 32-item evidence specification (`docs/EVIDENCE-SPEC.md`).
- Added Claude Code integration guide (`docs/CLAUDE-CODE-GUIDE.md`).
- Added initial pre-push git hook template.

## [1.0.0] - 2026-10-24
- Initial release of Five-Powers-Flow specification, core schemas, and governance templates.
