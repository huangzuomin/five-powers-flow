# -*- coding: utf-8 -*-
"""Contract #14-#16: only a fresh, matching merge event promotes a worktree."""
from __future__ import annotations

from datetime import datetime, timezone

from _h2_support import base_sha, init_repo

from packages.fpf_coordinator.worktree import marker as marker_mod
from packages.fpf_coordinator.worktree import promotion

NOW = datetime(2026, 11, 12, 1, 0, 0, tzinfo=timezone.utc)
HEAD = "a" * 40


def _marker(repo):
    return marker_mod.create(
        task_id="FPF2-H2-TEST", base_sha=base_sha(repo),
        owner={"login": "huangzuomin", "station": "ST-DEV-AUTHOR-01"},
        branch="refs/heads/fpf/test", work_order_id="WO-H2-TEST")


def _event(**over):
    event = {
        "type": "PR_MERGED",
        "task_id": "FPF2-H2-TEST",
        "event_id": "e" * 64,
        "sha": HEAD,
        "occurred_at": "2026-11-12T00:30:00.000000Z",
        "payload": {
            "pr_number": 123,
            "merge_commit_sha": "b" * 40,
            "head_sha": HEAD,
            "merged_at": "2026-11-12T00:30:00Z",
        },
    }
    event.update(over)
    return event


def _ledger(events, *, complete=True, as_of="2026-11-12T00:30:00Z"):
    return {
        "schema_version": "fpf.state-ledger/v1",
        "source": {"complete": complete, "as_of_event_id": "e" * 64,
                   "as_of_occurred_at": as_of},
        "tasks": [{"task_id": "FPF2-H2-TEST", "events": events}],
    }


def test_pr_merged_event_promotes_to_reclaimable(tmp_path):
    repo, _origin = init_repo(tmp_path)
    result = promotion.evaluate(_marker(repo), _ledger([_event()]),
                                head_sha=HEAD, now=NOW)
    assert result.promotes
    assert result.state == marker_mod.RECLAIMABLE
    assert result.merge_fact["pr_number"] == 123
    assert result.merge_fact["merge_commit_sha"] == "b" * 40


def test_ledger_stale_never_promotes(tmp_path):
    repo, _origin = init_repo(tmp_path)
    marker = _marker(repo)
    assert not promotion.evaluate(
        marker, None, head_sha=HEAD, now=NOW).promotes
    assert promotion.evaluate(
        marker, _ledger([_event()], complete=False), head_sha=HEAD,
        now=NOW).reason == promotion.LEDGER_STALE
    assert promotion.evaluate(
        marker, _ledger([_event()], as_of="2026-11-01T00:00:00Z"),
        head_sha=HEAD, now=NOW).reason == promotion.LEDGER_STALE


def test_event_task_mismatch_ignored(tmp_path):
    repo, _origin = init_repo(tmp_path)
    ledger = _ledger([_event(task_id="OTHER-TASK")])
    result = promotion.evaluate(_marker(repo), ledger, head_sha=HEAD, now=NOW)
    assert not result.promotes
    assert result.reason == "NO_MATCHING_MERGE_EVENT"


def test_event_for_other_pr_ignored(tmp_path):
    repo, _origin = init_repo(tmp_path)
    marker = _marker(repo)
    marker = dict(marker)
    marker["merge_fact"] = {
        "pr_number": 999, "merge_commit_sha": "c" * 40,
        "merged_at": "2026-11-01T00:00:00Z", "event_id": "f" * 64,
    }
    marker["digest"] = marker_mod.compute_digest(marker)
    result = promotion.evaluate(marker, _ledger([_event()]), head_sha=HEAD,
                               now=NOW)
    assert not result.promotes
