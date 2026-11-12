"""Static per-cell comparison of workflow permissions (F2 v3 §5, R7-01).

The rule the whole redesign rests on: a workflow that any ref can define may not
hold write permissions.  Write permissions are only legal behind triggers whose
definition is always taken from the default branch (`workflow_run`, `schedule`).
"""
from __future__ import annotations

from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"

READ_ONLY = {
    "contents": "read",
    "issues": "read",
    "pull-requests": "read",
    "actions": "read",
    "checks": "read",
    "metadata": "read",
}

# job -> exact permission set.  Unregistered jobs in registered files fail.
MATRIX = {
    "state-project.yml": {
        "project": {
            "contents": "read", "issues": "read",
            "pull-requests": "read", "actions": "read",
        },
    },
    "state-project-publish.yml": {
        "publish": {
            "contents": "write", "pull-requests": "write", "actions": "read",
            "issues": "read", "checks": "read",
        },
    },
    "state-audit.yml": {
        "audit": {
            "contents": "read", "checks": "write", "actions": "read",
            "issues": "read", "pull-requests": "read",
        },
    },
    "state-reconcile.yml": {
        "audit": {
            "contents": "read", "issues": "read",
            "pull-requests": "read", "actions": "read",
        },
    },
    "state-claim.yml": {
        "claim": {
            "contents": "write", "pull-requests": "read",
            "checks": "read", "actions": "read",
        },
    },
    "state-claim-trigger.yml": {
        "request": {"contents": "read"},
    },
    "state-claim-probe.yml": {
        "probe": {"contents": "write", "actions": "read"},
    },
    "state-claim-probe-trigger.yml": {
        "request": {"contents": "read"},
    },
}

TRIGGERS = {
    "state-audit.yml": {"schedule"},
    "state-project-publish.yml": {"workflow_run"},
    "state-claim.yml": {"workflow_run"},
    "state-claim-probe.yml": {"workflow_run"},
}


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def trigger_keys(document: dict) -> set[str]:
    # PyYAML parses the bare `on:` key as the boolean True.
    raw = document.get("on", document.get(True, {}))
    if isinstance(raw, str):
        return {raw}
    return set(raw or {})


def job_permissions(document: dict) -> dict[str, dict[str, str]]:
    return {
        name: dict(job.get("permissions") or {})
        for name, job in (document.get("jobs") or {}).items()
    }


class PermissionMatrixTests(unittest.TestCase):
    def test_write_jobs_have_a_zero_workflow_scope(self) -> None:
        for path in sorted(WORKFLOWS.glob("*.yml")):
            document = load(path.name)
            jobs = job_permissions(document)
            if not any("write" in perms.values() for perms in jobs.values()):
                continue
            self.assertIn("permissions", document, path.name)
            self.assertEqual(document["permissions"], {}, path.name)

    def test_no_workflow_scoped_write(self) -> None:
        for path in sorted(WORKFLOWS.glob("*.yml")):
            scoped = dict(load(path.name).get("permissions") or {})
            self.assertNotIn("write", set(scoped.values()), path.name)

    def test_registered_jobs_match_the_matrix_cell_by_cell(self) -> None:
        for name, expected_jobs in MATRIX.items():
            path = WORKFLOWS / name
            if not path.exists():
                continue
            document = load(name)
            actual = job_permissions(document)
            self.assertEqual(set(actual), set(expected_jobs), name)
            for job, expected in expected_jobs.items():
                self.assertEqual(actual[job], expected, f"{name}:{job}")

    def test_registered_triggers(self) -> None:
        for name, expected in TRIGGERS.items():
            path = WORKFLOWS / name
            if not path.exists():
                continue
            self.assertEqual(trigger_keys(load(name)), expected, name)

    def test_dispatchable_workflows_are_read_only(self) -> None:
        for path in sorted(WORKFLOWS.glob("*.yml")):
            document = load(path.name)
            if "workflow_dispatch" not in trigger_keys(document):
                continue
            for job, perms in job_permissions(document).items():
                for scope, level in perms.items():
                    self.assertEqual(level, "read", f"{path.name}:{job}:{scope}")
                    self.assertIn(scope, READ_ONLY)

    def test_schedule_and_dispatch_never_coexist(self) -> None:
        for path in sorted(WORKFLOWS.glob("*.yml")):
            keys = trigger_keys(load(path.name))
            self.assertFalse(
                {"schedule", "workflow_dispatch"} <= keys,
                f"{path.name} mixes schedule with dispatch",
            )

    def test_privileged_jobs_check_out_the_default_branch(self) -> None:
        for name in ("state-project-publish.yml", "state-audit.yml", "state-claim.yml"):
            path = WORKFLOWS / name
            if not path.exists():
                continue
            document = load(name)
            checkouts = [
                step for step in (document["jobs"][next(iter(document["jobs"]))]["steps"])
                if str(step.get("uses", "")).startswith("actions/checkout")
            ]
            self.assertTrue(checkouts, name)
            self.assertEqual((checkouts[0].get("with") or {}).get("ref"), "main", name)
            self.assertFalse(
                (checkouts[0].get("with") or {}).get("persist-credentials"), name,
            )


if __name__ == "__main__":
    unittest.main()
