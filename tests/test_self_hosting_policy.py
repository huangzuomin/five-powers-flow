"""Regression tests for the Issue #77 self-hosting protocol boundary.

These tests call the production policy, routing, gate, and hook functions.  The
temporary Git repository is only a fixture for exercising the production
anti-tamper boundary without mutating this checkout.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from packages.fpf_gates import hook_guard_dev, pre_handoff
from packages.fpf_policy.pr_gate import classify
from packages.fpf_policy.protected import is_protected, is_protected_tool_path


PROTOCOL_PATH = "docs/coordination/SELF-HOSTING-PROTOCOL.md"


def _git(cwd: Path, *args: str) -> tuple[int, str, str]:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


class TestSelfHostingPolicy(unittest.TestCase):
    def test_protocol_path_is_protected_after_normalization(self) -> None:
        for path in (
            "docs/coordination/self-hosting-protocol.md",
            r"docs\coordination\SELF-HOSTING-PROTOCOL.MD",
            "DOCS/COORDINATION/SeLf-HoStInG-PrOtOcOl.Md",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_protected(path))

    def test_protocol_absolute_tool_paths_are_protected(self) -> None:
        for path in (
            r"C:\candidate\docs\coordination\SELF-HOSTING-PROTOCOL.md",
            "/candidate/docs/coordination/SELF-HOSTING-PROTOCOL.md",
        ):
            with self.subTest(path=path):
                self.assertTrue(is_protected_tool_path(path))

    def test_dev_handoff_rejects_protocol_path_but_app_code_is_ordinary(self) -> None:
        with self.assertRaisesRegex(ValueError, "protected governance paths"):
            classify([PROTOCOL_PATH], "DEV_HANDOFF", set(), "feat/self-hosting")

        self.assertEqual(
            classify(["src/app.py"], "DEV_HANDOFF", set(), "feat/application"),
            "CODE_PR",
        )
        self.assertFalse(is_protected("src/app.py"))

    def test_policy_change_on_protocol_path_routes_to_gate_pr(self) -> None:
        self.assertEqual(
            classify([PROTOCOL_PATH], "POLICY_CHANGE", set(), "fpf/self-hosting-protocol-20261101"),
            "GATE_PR",
        )

    def test_policy_change_for_ordinary_documentation_remains_policy_pr(self) -> None:
        self.assertEqual(
            classify(["docs/design-note.md"], "POLICY_CHANGE", set(), "feat/documentation"),
            "POLICY_PR",
        )

    def test_pre_handoff_gate_3_rejects_protocol_path_from_temp_git_diff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            self.assertEqual(_git(repo, "init", "-b", "main")[0], 0)
            self.assertEqual(_git(repo, "config", "user.name", "FPF test")[0], 0)
            self.assertEqual(_git(repo, "config", "user.email", "fpf-test@example.invalid")[0], 0)
            (repo / "README.md").write_text("# fixture\n", encoding="utf-8")
            self.assertEqual(_git(repo, "add", "README.md")[0], 0)
            self.assertEqual(_git(repo, "commit", "-m", "initial")[0], 0)
            self.assertEqual(_git(repo, "checkout", "-b", "candidate")[0], 0)

            protocol = repo / PROTOCOL_PATH
            protocol.parent.mkdir(parents=True, exist_ok=True)
            protocol.write_text("candidate change\n", encoding="utf-8")
            self.assertEqual(_git(repo, "add", PROTOCOL_PATH)[0], 0)
            self.assertEqual(_git(repo, "commit", "-m", "candidate")[0], 0)

            def run_in_fixture(command: list[str]) -> tuple[int, str, str]:
                return _git(repo, *command[1:]) if command and command[0] == "git" else _git(repo, *command)

            with patch.object(pre_handoff, "run_cmd", side_effect=run_in_fixture):
                self.assertFalse(pre_handoff.gate_3_project_map_anti_tamper(base_branch="main"))

    def test_hook_guard_blocks_edit_write_and_notebookedit_on_protocol_path(self) -> None:
        for tool_name in ("Edit", "Write", "NotebookEdit"):
            payload = {
                "tool_name": tool_name,
                "tool_input": {
                    "file_path": r"D:\candidate\docs\coordination\SELF-HOSTING-PROTOCOL.md",
                },
            }
            with self.subTest(tool_name=tool_name):
                self.assertEqual(hook_guard_dev.check_pre_tool_use(payload), 2)

        self.assertEqual(
            hook_guard_dev.check_pre_tool_use(
                {"tool_name": "Edit", "tool_input": {"file_path": "src/app.py"}}
            ),
            0,
        )

    def test_protocol_is_utf8_and_contains_exactly_ten_core_chapters(self) -> None:
        protocol_file = Path(__file__).resolve().parents[1] / PROTOCOL_PATH
        raw = protocol_file.read_bytes()
        text = raw.decode("utf-8")
        self.assertNotIn("\ufffd", text)
        self.assertNotRegex(text, r"(?im)\b(?:TODO|TBD)\b")

        chapter_markers = (
            "## 1. 目的、适用范围、术语和规范优先级",
            "## 2. Controller N / Candidate N+1 双版本模型与信任根",
            "## 3. 自举研发生命周期：目标输入、设计、授权、Admission、DEV、独立 QA、人工合并、晋升、观察、回滚",
            "## 4. 五权分立和角色身份隔离",
            "## 5. 任务树与授权派生规则",
            "## 6. 自我修改风险分级和特殊审查",
            "## 7. 执行环境、凭据、分支、Worktree、状态账本和证据隔离",
            "## 8. Candidate 晋升条件、兼容性、迁移与回滚",
            "## 9. 失败、未知状态、停止条件和人工接管",
            "## 10. L1/L2/L3 能力等级及禁止夸大成熟度的声明规则",
        )
        for marker in chapter_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

        required_terms = (
            "不可变 commit SHA",
            "独立 branch、独立 Git Worktree 和独立 execution environment",
            "不得控制、修改、替换或批准 Controller N",
            "禁止原地自更新",
            "不是第六权",
            "父 mandate only narrows",
            "普通功能",
            "Runtime / 协调核心",
            "治理 / 授权 / QA / 合并规则",
            "branch protection",
            "CODEOWNERS",
            "Secrets",
            "Runner trust root",
            "approval conditions",
            "固定 SHA",
            "独立 QA",
            "真实证据",
            "`NOT_RUN`",
            "failure fuse",
            "回滚",
            "L1 单切片",
            "L2 Feature 多切片",
            "L3 多项目组织自治",
            "A1_CREATE_CANDIDATE_BRANCH",
            "A2_CREATE_ISOLATED_WORKTREE",
            "A3_RESTRICTED_EDIT_ALLOWED_PATHS",
            "A4_EXECUTE_LOCAL_TESTS",
            "A5_CREATE_DEV_COMMIT",
            "A6_PUSH_CANDIDATE_BRANCH",
            "A7_CREATE_GATE_PR",
            "`POLICY_CHANGE`",
            "`GATE_PR`",
            "runtime autonomy",
            "两个、不可代理的人类主权闸门",
        )
        for term in required_terms:
            with self.subTest(term=term):
                self.assertIn(term, text)


if __name__ == "__main__":
    unittest.main()
