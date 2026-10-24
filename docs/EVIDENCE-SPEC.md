# FPF 32 项标准证据包规范 (32-Item Evidence Pack Specification)

> **规范编号**：`FPF-SPEC-EVIDENCE-32`  
> **所属协议**：FPF-RFC-001  
> **核心原则**：口说无凭，无原始日志与外部哈希锚点一律判定为 `INVALID_TEST`。

---

## 一、 为什么必须有标准证据包？

在多智能体自动化工程中，LLM 最常见的作弊手段是：
1. **打卡式虚报**：宣称“所有接口已测试通过”，但给不出任何原始标准输出与退出码；
2. **测试空跑**：由于 Mock 路径写错或版本升级，测试脚本根本没走断言逻辑，直接以退出码 0 返回；
3. **本地脏数据污染**：测试跑在开发者本地脏环境，换一台机器或 CI 立即崩溃。

FPF 规定：**独立 QA 工位验收时，必须生成包含 32 项确定性证据的封存包（Evidence Pack），并通过 `manifest.json` 固化为唯一的 SHA-256 主锚点。**

---

## 二、 32 项证据完整清单

| 分类 | 编号 | 证据项标识 | 格式与内容要求 | 产出角色 |
| :--- | :--- | :--- | :--- | :--- |
| **A. 元数据与代码基线** | 01 | `EVID-01-TASK-META` | 包含 `task_id`, `pr_url`, 时间戳的元数据卡片 | DEV / QA |
| | 02 | `EVID-02-BASELINE-SHA` | 40 位父提交 Commit SHA（`git rev-parse HEAD~1`） | DEV |
| | 03 | `EVID-03-TESTED-CODE-SHA` | 40 位固定提测 Commit SHA（`git rev-parse HEAD`） | DEV |
| | 04 | `EVID-04-GIT-DIFF-STAT` | 相比基线的变更统计输出（`git diff --stat`） | DEV |
| **B. 物理环境隔离凭据** | 05 | `EVID-05-RUNNER-OS` | 操作系统架构与内核版本（`uname -a` 或 Windows 系统信息） | QA |
| | 06 | `EVID-06-RUNTIME-VERSION` | 语言运行时版本（`python --version`, `node -v`） | QA |
| | 07 | `EVID-07-WORKTREE-PATH` | 独立的 Worktree 绝对路径记录（证明非原开发工作区） | QA |
| | 08 | `EVID-08-CLEAN-GIT-STATUS` | 运行前工作树 `git status --porcelain` 为空的快照 | QA |
| **C. 契约与静态门禁** | 09 | `EVID-09-LINT-STDOUT` | 代码静态检查工具的标准输出与 0 退出码 | DEV |
| | 10 | `EVID-10-TYPECHECK-STDOUT` | 类型检查（TypeScript / mypy）的完整输出 | DEV |
| | 11 | `EVID-11-SCHEMA-DIFF` | 接口契约与前端 SDK 的零差异对比凭据 | DEV |
| | 12 | `EVID-12-UNTRACKED-AUDIT` | 确保无敏感密钥或未追踪文件的审计快照 | DEV |
| **D. 依赖与数据库隔离** | 13 | `EVID-13-LOCKFILE-HASH` | 依赖锁定文件（`pnpm-lock.yaml` / `poetry.lock`）哈希 | QA |
| | 14 | `EVID-14-DB-INSTANCE-PORT` | 本次测试分配的临时数据库独立随机端口凭据 | QA |
| | 15 | `EVID-15-MIGRATION-UP` | 数据库升级迁移应用的完整 stdout 日志 | QA |
| | 16 | `EVID-16-MIGRATION-DOWN` | 数据库回滚测试通过的完整 stdout 日志 | QA |
| **E. 0% Mock 真实集成** | 17 | `EVID-17-SVC-STARTUP` | 后端服务在隔离端口真实启动的就绪日志 | QA |
| | 18 | `EVID-18-API-REQUEST-DUMP` | 测试发出的真实 HTTP 请求抓包或请求体 DUMP | QA |
| | 19 | `EVID-19-API-RESPONSE-DUMP`| 服务端返回的真实 HTTP 响应状态码与响应体 DUMP | QA |
| | 20 | `EVID-20-DB-PERSIST-CHECK` | 直接通过 SQL 查询数据库验证数据落盘的原始记录 | QA |
| **F. 端到端与交互验证** | 21 | `EVID-21-E2E-RUNNER-LOG` | Playwright / Cypress 执行套件完整控制台输出 | QA |
| | 22 | `EVID-22-E2E-SCREENSHOT` | 关键业务结果页面的全尺寸渲染截图（PNG 格式） | QA |
| | 23 | `EVID-23-BROWSER-CONSOLE` | 浏览器运行时控制台错误日志（必须为 0 错误） | QA |
| | 24 | `EVID-24-DOM-ASSERT-DUMP` | 页面核心 DOM 节点的选择器断言匹配证据 | QA |
| **G. 红绿变异对抗反证** | 25 | `EVID-25-RED-REPLAY-CMD` | 变异对抗回退到旧代码的执行命令 | QA |
| | 26 | `EVID-26-RED-FAIL-STDOUT` | 确认旧代码在同一用例下确凿失败（退出码非 0）的日志 | QA |
| | 27 | `EVID-27-GREEN-PASS-STDOUT`| 确认修复代码在同一用例下确凿通过（退出码 0）的日志 | QA |
| | 28 | `EVID-28-MUTATION-DIFF` | 变异测试用例的设计差异比对凭据 | QA |
| **H. 诚实申报与主锚点** | 29 | `EVID-29-NOT-RUN-LIST` | 明确未覆盖项及客观受阻原因的声明文件 | DEV / QA |
| | 30 | `EVID-30-KNOWN-RISKS` | 本切片已知缺陷或遗留边界风险记录 | DEV / QA |
| | 31 | `EVID-31-MANIFEST-ITEMS` | 包含上述 1~30 项所有文件 SHA-256 的清册表 | QA |
| | 32 | `EVID-32-MASTER-ANCHOR` | 对 `EVID-31` 整体计算生成的 64 位 SHA-256 主锚点 | QA |

---

## 三、 主锚点校验机制 (The Master Anchor)

在 `QA_RESULT` 卡片中填写的：
```yaml
evidence_manifest_sha256: "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
```
必须能够通过以下命令在独立工位 100% 验证重现：
```bash
sha256sum docs/evidence/manifest.json
# 输出必须与 QA_RESULT 卡中的主哈希完全一致
```
若主锚点哈希不匹配，中立协调器将判定裁决为 `INVALID_TEST`，直接拒绝流转。
