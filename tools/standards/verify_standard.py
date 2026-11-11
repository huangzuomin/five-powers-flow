"""Deterministic verifier for FPF-STANDARD-2.0."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


STANDARD_REL = Path("docs/standards/FPF-STANDARD-2.0.md")
ROADMAP_REL = Path("docs/roadmap/FPF-2.0-STANDARDIZATION-ROADMAP.md")
ASSERTIONS_REL = Path("tools/standards/standard-assertions.json")
CLAUSE_PREFIXES = ("GOV", "PLN", "CTR", "EVT", "EVD", "PRD", "CMP", "ACC")
METADATA_KEYS = (
    "standard_id",
    "version",
    "status",
    "date",
    "task_id",
    "base_sha",
    "supersedes/derives_from",
    "normative_source",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_bytes(root: Path, relative: Path) -> tuple[bytes, bool]:
    try:
        return (root / relative).read_bytes(), True
    except (OSError, ValueError):
        return b"", False


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def _load_assertions(data: bytes) -> tuple[dict[str, Any], bool]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}, False
    return (value, isinstance(value, dict))


def _metadata(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    row_pattern = re.compile(r"(?m)^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|")
    for key, value in row_pattern.findall(text):
        clean_key = key.strip().strip("`")
        clean_value = value.strip().strip("`")
        if clean_key and not set(clean_key) <= {"-"}:
            values[clean_key] = clean_value
    return values


def _between(text: str, start_pattern: str, end_pattern: str) -> str:
    lines = text.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if re.match(start_pattern, line)),
        None,
    )
    if start is None:
        return ""
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if re.match(end_pattern, lines[index])
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def _clause_ids(text: str) -> list[str]:
    pattern = re.compile(
        r"(?m)(?:^|\|\s*)\*\*((?:GOV|PLN|CTR|EVT|EVD|PRD|CMP|ACC)-\d{2})（"
    )
    return pattern.findall(text)


def _acc_lines(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\*\*(ACC-\d{2})（", line)
        if match:
            result[match.group(1)] = line
    return result


def _section_numbers(text: str) -> set[str]:
    return set(re.findall(r"(?m)^#{2,4}\s+(\d+(?:\.\d+)*)\b", text))


def _check(checks: list[dict[str, str]], check_id: str, passed: bool, detail: str) -> None:
    checks.append(
        {
            "id": check_id,
            "result": "PASS" if passed else "FAIL",
            "detail": detail,
        }
    )


def verify_repo(repo: Path) -> tuple[dict[str, Any], bytes]:
    root = Path(repo)
    assertions_bytes, assertions_exists = _read_bytes(root, ASSERTIONS_REL)
    document_bytes, document_exists = _read_bytes(root, STANDARD_REL)
    roadmap_bytes, roadmap_exists = _read_bytes(root, ROADMAP_REL)
    assertions, assertions_valid = _load_assertions(assertions_bytes)
    document = _decode(document_bytes)
    roadmap = _decode(roadmap_bytes)
    checks: list[dict[str, str]] = []

    metadata_expected = {
        key: assertions.get(key) for key in METADATA_KEYS
    }
    metadata_actual = _metadata(document)
    metadata_ok = (
        assertions_exists
        and assertions_valid
        and document_exists
        and roadmap_exists
        and all(metadata_actual.get(key) == value for key, value in metadata_expected.items())
    )
    _check(
        checks,
        "metadata_binding",
        metadata_ok,
        "标准元数据与断言清单一致" if metadata_ok else "标准元数据、断言清单或输入文件不一致",
    )

    expected_sections = assertions.get("expected_sections", [])
    actual_sections = [
        line.strip()
        for line in document.splitlines()
        if re.match(r"^##\s+", line) and not re.match(r"^###", line)
    ]
    sections_ok = actual_sections == expected_sections
    _check(
        checks,
        "section_order",
        sections_ok,
        f"二级标题 {len(actual_sections)}/{len(expected_sections)}，顺序一致"
        if sections_ok
        else "二级标题数量或顺序与断言不一致",
    )

    clauses_text = _between(document, r"^## 3\.", r"^## 9\.")
    clause_ids = _clause_ids(clauses_text)
    clause_counts = {
        prefix: sum(clause_id.startswith(prefix + "-") for clause_id in clause_ids)
        for prefix in CLAUSE_PREFIXES
    }
    expected_counts = assertions.get("clause_counts", {})
    clauses_ok = (
        len(clause_ids) == len(set(clause_ids))
        and clause_counts == expected_counts
    )
    _check(
        checks,
        "clause_counts",
        clauses_ok,
        f"条款定义 {len(clause_ids)} 条，编号唯一且计数一致"
        if clauses_ok
        else "条款编号不唯一或计数与断言不一致",
    )

    section8 = _between(document, r"^## 8\.", r"^## 9\.")
    acc_ids = re.findall(r"(?m)^\*\*(ACC-\d{2})（", section8)
    expected_acc_ids = [f"ACC-{index:02d}" for index in range(1, 14)]
    acc_continuous = acc_ids == expected_acc_ids
    _check(
        checks,
        "acc_continuity",
        acc_continuous,
        "ACC-01 至 ACC-13 连续且各定义一次"
        if acc_continuous
        else "ACC 条款未形成 ACC-01 至 ACC-13 的连续序列",
    )

    acc_lines = _acc_lines(section8)
    acc07 = acc_lines.get("ACC-07", "")
    acc07_phrases = assertions.get("acc07_required_phrases", [])
    acc07_ok = bool(acc07) and all(phrase in acc07 for phrase in acc07_phrases)
    _check(
        checks,
        "acc07_required_phrases",
        acc07_ok,
        "ACC-07 五处限定语全部存在" if acc07_ok else "ACC-07 缺少断言限定语",
    )

    acc08 = acc_lines.get("ACC-08", "")
    acc08_dimensions = assertions.get("acc08_dimensions", [])
    acc08_ok = bool(acc08) and all(dimension in acc08 for dimension in acc08_dimensions)
    _check(
        checks,
        "acc08_dimensions",
        acc08_ok,
        "ACC-08 五维名称全部存在" if acc08_ok else "ACC-08 缺少证据维度名称",
    )

    planes = assertions.get("six_planes", [])
    roadmap_headings = {
        number: heading
        for number, heading in re.findall(
            r"(?m)^###\s+(\d+\.\d+)\s+(.+?)\s*$", roadmap
        )
    }
    standard_plane_headings = re.findall(
        r"(?m)^###\s+4\.\d+\s+(.+?)\s*$", document
    )
    missing_planes: list[str] = []
    for plane in planes:
        name = plane.get("name", "")
        section = str(plane.get("roadmap_section", "")).lstrip("§")
        roadmap_heading = roadmap_headings.get(section, "")
        roadmap_ok = roadmap_heading.startswith(name + "：") or roadmap_heading == name
        standard_ok = any(
            heading.startswith(name + "（") or heading.startswith(name + "：") or heading == name
            for heading in standard_plane_headings
        )
        if not (roadmap_ok and standard_ok):
            missing_planes.append(name or section)
    planes_ok = len(planes) == 6 and not missing_planes
    _check(
        checks,
        "six_planes",
        planes_ok,
        "六平面名称与路线图 §3.1–§3.6 标题一致"
        if planes_ok
        else "六平面名称或路线图小节映射不完整",
    )

    source_markers = re.findall(r"（源：([^）]+)）", document)
    roadmap_sections = _section_numbers(roadmap)
    source_refs = [
        reference
        for marker in source_markers
        for reference in re.findall(r"§(\d+(?:\.\d+)*)", marker)
    ]
    unparsed_sources = [
        marker for marker in source_markers if not re.search(r"§\d+(?:\.\d+)*", marker)
    ]
    missing_sources = sorted(
        set(source_refs) - roadmap_sections,
        key=lambda value: tuple(int(part) for part in value.split(".")),
    )
    sources_ok = bool(source_markers) and not unparsed_sources and not missing_sources
    _check(
        checks,
        "source_references",
        sources_ok,
        "全部源标记均解析到路线图章节"
        if sources_ok
        else "存在无法解析或不在路线图中的源章节",
    )

    forbidden = assertions.get("forbidden_phrases", [])
    forbidden_hits = sorted(phrase for phrase in forbidden if phrase in document)
    _check(
        checks,
        "forbidden_phrases",
        not forbidden_hits,
        "禁止词命中数为 0" if not forbidden_hits else "存在禁止词命中",
    )

    required_levels = assertions.get("required_levels", [])
    term_line_match = re.search(r"(?m)^\*\*TRM-01（MUST）\*\*.*$", document)
    term_line = term_line_match.group(0) if term_line_match else ""
    levels_ok = all(
        f"`{level}`" in term_line and f"（{level}）" in document
        for level in required_levels
    )
    _check(
        checks,
        "normative_levels",
        levels_ok,
        "MUST/SHOULD/MAY 均已定义并使用" if levels_ok else "规范等级定义或使用不完整",
    )

    required_boundaries = assertions.get("required_boundaries", [])
    boundaries_ok = all(boundary in document for boundary in required_boundaries)
    _check(
        checks,
        "status_boundaries",
        boundaries_ok,
        "PLAN_ONLY 与 NOT_AUTHORIZED 均已声明"
        if boundaries_ok
        else "未找到全部必备状态边界",
    )

    roadmap_section10 = _between(roadmap, r"^## 10\.", r"^## 11\.")
    roadmap_items = re.findall(r"(?m)^\s*(\d+)\.\s+", roadmap_section10)
    expected_items = int(assertions.get("roadmap_section10_items", 0) or 0)
    acc_source_items = assertions.get("acc_source_items", {})
    missing_acc_refs = [
        str(index)
        for index in range(1, expected_items + 1)
        if not any(
            str(acc_source_items.get(f"ACC-{acc_index:02d}", "")) == f"§10 第 {index} 条"
            and f"§10 第 {index} 条" in acc_lines.get(f"ACC-{acc_index:02d}", "")
            for acc_index in range(1, 14)
        )
    ]
    section10_ok = (
        len(roadmap_items) == expected_items
        and roadmap_items == [str(index) for index in range(1, expected_items + 1)]
        and not missing_acc_refs
    )
    _check(
        checks,
        "roadmap_section10",
        section10_ok,
        "路线图 §10 恰有 13 条且逐条被 ACC 引用"
        if section10_ok
        else "路线图 §10 数量、顺序或 ACC 引用不完整",
    )

    passed = sum(check["result"] == "PASS" for check in checks)
    failed = len(checks) - passed
    payload: dict[str, Any] = {
        "checks": checks,
        "summary": {
            "failed": failed,
            "passed": passed,
            "result": "PASS" if failed == 0 else "FAIL",
            "total": len(checks),
        },
        "document_sha256": _sha256(document_bytes),
        "roadmap_sha256": _sha256(roadmap_bytes),
        "assertions_sha256": _sha256(assertions_bytes),
    }
    serialized = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")
    return payload, serialized


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="验证 FPF-STANDARD-2.0 文档")
    parser.add_argument("--repo", default=".", help="仓库根目录（缺省为当前工作目录）")
    parser.add_argument("--out", help="同时写出确定性 JSON 的路径")
    args = parser.parse_args(argv)

    payload, serialized = verify_repo(Path(args.repo))
    if args.out:
        Path(args.out).write_bytes(serialized)
    sys.stdout.buffer.write(serialized)
    sys.stdout.buffer.flush()
    return 0 if payload["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
