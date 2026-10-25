# Evidence examples — NOT execution evidence

Previous versions placed fabricated/placeholder bytes under docs/evidence/ and
described them as an executable QA evidence package. The hashes did not match
the files, and the so-called logs consisted of "PASS" prose only. These files
have been removed to prevent reuse as signed evidence.

A genuine QA evidence package must be produced by an independent test runner
against a fixed PR head, from real command stdout/stderr and exit status,
stored outside the DEV checkout (prefer immutable CI artifacts). A SHA-256
only protects bytes after their source and runner have been authenticated.
Never copy a manifest digest, author string, or PASS from a previous PR.

Reference structure (field names only, no made-up hashes):

- QA_RESULT: task_id, tested_sha, runner_sha, qa_contract_sha,
  authenticated reviewer, profile, checks, and a verified evidence anchor.
- manifest: manifest_version, task_id, profile, items[id/path/sha256].
- Real physical files named by every mandatory EVID-XX entry; independently
  collected by the chosen runner and verified by the evaluator.

See docs/EVIDENCE-SPEC.md for the required evidence profile and meaning
of each EVID ID. This page is intentionally *not* an executable example.
