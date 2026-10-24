# Changelog

All notable changes to the **Five-Powers-Flow (FPF)** project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
