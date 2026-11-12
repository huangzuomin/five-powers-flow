# -*- coding: utf-8 -*-
"""Contract #11-#13: the marker is written, complete, and tamper-evident."""
from __future__ import annotations

import json

import pytest

from _h2_support import base_sha, init_repo

from packages.fpf_coordinator.worktree import marker as marker_mod


def _valid(repo):
    return marker_mod.create(
        task_id="FPF2-H2-TEST", base_sha=base_sha(repo),
        owner={"login": "huangzuomin", "station": "ST-DEV-AUTHOR-01"},
        branch="refs/heads/main", work_order_id="WO-H2-TEST")


def test_create_writes_marker(tmp_path):
    repo, _origin = init_repo(tmp_path)
    written = marker_mod.write(repo, _valid(repo))
    assert written.name == marker_mod.MARKER_NAME
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "fpf.worktree-marker/v1"
    assert payload["state"] == "ACTIVE"
    assert payload["state_history"][0]["state"] == "ACTIVE"
    assert len(payload["digest"]) == 64
    assert marker_mod.read(repo)["task_id"] == "FPF2-H2-TEST"


def test_marker_requires_all_fields(tmp_path):
    repo, _origin = init_repo(tmp_path)
    complete = _valid(repo)
    required = [field for field in marker_mod.FIELDS
                if field not in ("digest", "bootstrap")]
    for field in required:
        broken = dict(complete)
        broken.pop(field)
        with pytest.raises(marker_mod.MissingField) as excinfo:
            marker_mod.validate(broken)
        assert field in str(excinfo.value)


def test_marker_digest_detects_hand_edit(tmp_path):
    repo, _origin = init_repo(tmp_path)
    marker_mod.write(repo, _valid(repo))
    path = repo / marker_mod.MARKER_NAME
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["task_id"] = "FPF2-H2-FORGED"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(marker_mod.MarkerTampered):
        marker_mod.read(repo)


def test_marker_rejects_unknown_fields(tmp_path):
    repo, _origin = init_repo(tmp_path)
    payload = dict(_valid(repo))
    payload["authorized_by"] = "self"
    with pytest.raises(marker_mod.UnknownField):
        marker_mod.validate(payload)


def test_marker_ttl_bounds(tmp_path):
    repo, _origin = init_repo(tmp_path)
    for ttl in (0, 31):
        with pytest.raises(marker_mod.InvalidMarker):
            marker_mod.create(
                task_id="FPF2-H2-TEST", base_sha=base_sha(repo),
                owner={"login": "huangzuomin", "station": "ST-DEV-AUTHOR-01"},
                branch="refs/heads/main", work_order_id="WO-H2-TEST",
                ttl_days=ttl)


def test_marker_requires_registered_station(tmp_path):
    repo, _origin = init_repo(tmp_path)
    (repo / ".fpf").mkdir(exist_ok=True)
    (repo / ".fpf" / "stations.yaml").write_text(
        "stations:\n  - id: ST-DEV-AUTHOR-01\n", encoding="utf-8")
    with pytest.raises(marker_mod.InvalidMarker):
        marker_mod.create(
            task_id="FPF2-H2-TEST", base_sha=base_sha(repo),
            owner={"login": "huangzuomin", "station": "ST-UNKNOWN-99"},
            branch="refs/heads/main", work_order_id="WO-H2-TEST",
            stations_path=repo / ".fpf" / "stations.yaml")
