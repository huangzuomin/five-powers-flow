"""Station registry: who is allowed to sign what on a gated route (G2).

The registry is read from the **base** commit of the pull request, never from
the candidate head. A change set that rewrites the registry therefore cannot
grant itself authority: it is judged by the registry that was already merged,
and its new relations take effect only after the merge.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml


REGISTRY_PATH = ".fpf/stations.yaml"

VALID_KINDS = frozenset({"dev", "qa", "qa-evidence", "ruling-carrier", "planner"})

# A PR author must never resolve to one of these: it would make the author a
# reviewer of their own work.
QA_KINDS = frozenset({"qa", "qa-evidence", "ruling-carrier"})


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader that refuses duplicate mapping keys instead of keeping the last."""


def _construct_unique_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise ValueError(f"duplicate key {key!r} in station registry")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


@dataclass(frozen=True)
class Station:
    id: str
    kind: str
    carriers: tuple[str, ...]


class Registry:
    def __init__(self, stations: Iterable[Station]) -> None:
        self.stations = tuple(stations)
        self._by_login = {}
        for station in self.stations:
            for carrier in station.carriers:
                self._by_login[carrier] = station

    def resolve(self, login: str) -> Station | None:
        return self._by_login.get(str(login or "").strip().casefold())

    def require(self, login: str, kinds: Iterable[str], context: str) -> Station:
        expected = sorted(kinds)
        station = self.resolve(login)
        if station is None:
            raise ValueError(
                f"{context} '{login}' is not a registered station "
                f"(expected kind {expected})"
            )
        if station.kind not in expected:
            raise ValueError(
                f"{context} '{login}' is registered as '{station.kind}', "
                f"expected kind {expected}"
            )
        return station

    def reject_qa_kind(self, login: str, context: str) -> None:
        station = self.resolve(login)
        if station is not None and station.kind in QA_KINDS:
            raise ValueError(
                f"{context} '{login}' is registered as '{station.kind}', "
                "which is a QA station"
            )


def parse(text: str) -> Registry:
    """Parse and fully validate a registry document. Any defect is fail-closed."""
    try:
        data = yaml.load(text, Loader=_UniqueKeyLoader)
    except ValueError:
        raise
    except yaml.YAMLError as exc:
        raise ValueError(f"station registry is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("station registry must be a mapping (fail closed)")
    if data.get("version") != 1:
        raise ValueError(
            f"station registry version must be 1, got {data.get('version')!r} (fail closed)"
        )
    entries = data.get("stations")
    if not isinstance(entries, list) or not entries:
        raise ValueError("station registry must declare a non-empty 'stations' list (fail closed)")

    seen_ids: set[str] = set()
    seen_carriers: dict[str, str] = {}
    stations: list[Station] = []
    for index, entry in enumerate(entries):
        where = f"stations[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{where} must be a mapping (fail closed)")
        station_id = entry.get("id")
        if not isinstance(station_id, str) or not station_id.strip():
            raise ValueError(f"{where} has an empty 'id' (fail closed)")
        station_id = station_id.strip()
        if station_id in seen_ids:
            raise ValueError(f"duplicate station id '{station_id}' (fail closed)")
        kind = entry.get("kind")
        if kind not in VALID_KINDS:
            raise ValueError(
                f"{where} has unknown kind {kind!r}; expected one of {sorted(VALID_KINDS)}"
            )
        carriers = entry.get("carriers")
        if not isinstance(carriers, list) or not carriers:
            raise ValueError(f"{where} must declare a non-empty 'carriers' list (fail closed)")
        normalized: list[str] = []
        for carrier in carriers:
            if not isinstance(carrier, dict):
                raise ValueError(f"{where} carrier must be a mapping (fail closed)")
            if carrier.get("type") != "github-login":
                raise ValueError(
                    f"{where} carrier type must be 'github-login', got {carrier.get('type')!r}"
                )
            value = carrier.get("value")
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{where} carrier has an empty 'value' (fail closed)")
            login = value.strip().casefold()
            if login in seen_carriers:
                raise ValueError(
                    f"carrier '{value.strip()}' is registered more than once "
                    f"(stations '{seen_carriers[login]}' and '{station_id}') (fail closed)"
                )
            seen_carriers[login] = station_id
            normalized.append(login)
        seen_ids.add(station_id)
        stations.append(Station(station_id, kind, tuple(normalized)))
    return Registry(stations)


def load_registry(repo_dir: Path | str, base_sha: str) -> Registry:
    """Read the registry from the PR base commit, never from the working tree."""
    base_sha = str(base_sha or "").strip().lower()
    if not base_sha:
        raise ValueError("station registry cannot be resolved without a base SHA (fail closed)")
    proc = subprocess.run(
        ["git", "show", f"{base_sha}:{REGISTRY_PATH}"],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    if proc.returncode != 0:
        raise ValueError(
            f"station registry missing on base {base_sha} ({REGISTRY_PATH}) (fail closed)"
        )
    return parse(proc.stdout)
