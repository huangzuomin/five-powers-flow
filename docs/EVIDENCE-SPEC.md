# FPF 32 项标准证据包规范 (32-Item Evidence Pack Specification)

> **规范编号**：`FPF-SPEC-EVIDENCE-32`  
> **所属协议**：FPF-RFC-001 v1.2.1  
> **核心原则**：口说无凭，无原始日志与外部哈希锚点一律判定为 `INVALID_TEST`。  
> **反教条分级**：按切片类型划分 Profile，严禁为了凑数伪造无意义假动作。

---

## 一、 证据包分级体系 (Evidence Profiles)

为防止非 Web/非数据库切片为凑齐 32 项而伪造浏览器截图或空跑数据库脚本，FPF 引入 **4 大标准 Profile 声明机制**：

| Profile 标识 | 适用切片类型 | 核心要求项 | 免除项 (允许标 N/A) |
| :--- | :--- | :--- | :--- |
| **`PROFILE-LIBRARY`** | 纯算法、基础包、命令行工具 | A(元数据) + C(静态门禁) + D(依赖锁) + H(主锚点) | 数据库项(14~16, 20)、端到端项(21~24) |
| **`PROFILE-API-DB`** | 后端服务、数据模型与持久层 | A + B(环境) + C + D(独立临时DB) + E(真实集成) + H | 浏览器项(21~24) |
| **`PROFILE-FULLSTACK`** | 包含前台交互、完整业务流 | **全量 32 项完整执行**，含真实浏览器截图 | 无 |
| **`PROFILE-REWORK`** | 任何缺陷修复轮次 (Bug-Fix) | 根据模块选择上述之一，**强制追加 G(红绿变异反证)** | 视基础 Profile 而定 |

*注：在任何 Profile 中免除的项，必须在 `manifest.json` 中明确声明为 `STATUS: NOT_APPLICABLE` 并附带架构合理性说明。*

---

## 二、 32 项证据完整清单

| 分类 | 编号 | 证据项标识 | 格式与内容要求 | 产出角色 | 适用 Profile |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A. 元数据与代码基线** | 01 | `EVID-01-TASK-META` | 包含 `task_id`, `pr_url`, 时间戳的元数据卡片 | DEV / QA | ALL |
| | 02 | `EVID-02-BASELINE-SHA` | 40 位父提交 Commit SHA（`git rev-parse HEAD~1`） | DEV | ALL |
| | 03 | `EVID-03-TESTED-CODE-SHA` | 40 位固定提测 Commit SHA（`git rev-parse HEAD`） | DEV | ALL |
| | 04 | `EVID-04-GIT-DIFF-STAT` | 相比基线的变更统计输出（`git diff --stat`） | DEV | ALL |
| **B. 物理环境隔离凭据** | 05 | `EVID-05-RUNNER-OS` | 操作系统架构与内核版本（`uname -a` 或 Windows 系统信息） | QA | ALL |
| | 06 | `EVID-06-RUNTIME-VERSION` | 语言运行时版本（`python --version`, `node -v`） | QA | ALL |
| | 07 | `EVID-07-WORKTREE-PATH` | 独立的 Worktree 绝对路径记录（证明非原开发工作区） | QA | ALL |
| | 08 | `EVID-08-CLEAN-GIT-STATUS` | 运行前工作树 `git status --porcelain` 为空的快照 | QA | ALL |
| **C. 契约与静态门禁** | 09 | `EVID-09-LINT-STDOUT` | 代码静态检查工具的标准输出与 0 退出码 | DEV | ALL |
| | 10 | `EVID-10-TYPECHECK-STDOUT` | 类型检查（TypeScript / mypy）的完整输出 | DEV | ALL |
| | 11 | `EVID-11-SCHEMA-DIFF` | 接口契约与前端 SDK 的零差异对比凭据 | DEV | API-DB / FULLSTACK |
| | 12 | `EVID-12-UNTRACKED-AUDIT` | 确保无敏感密钥或未追踪文件的审计快照 | DEV | ALL |
| **D. 依赖与数据库隔离** | 13 | `EVID-13-LOCKFILE-HASH` | 依赖锁定文件（`pnpm-lock.yaml` / `poetry.lock`）哈希 | QA | ALL |
| | 14 | `EVID-14-DB-INSTANCE-PORT` | 本次测试分配的临时数据库独立随机端口凭据 | QA | API-DB / FULLSTACK |
| | 15 | `EVID-15-MIGRATION-UP` | 数据库升级迁移应用的完整 stdout 日志 | QA | API-DB / FULLSTACK |
| | 16 | `EVID-16-MIGRATION-DOWN` | 数据库回滚测试通过的完整 stdout 日志 | QA | API-DB / FULLSTACK |
| **E. 0% Mock 真实集成** | 17 | `EVID-17-SVC-STARTUP` | 后端服务在隔离端口真实启动的就绪日志 | QA | API-DB / FULLSTACK |
| | 18 | `EVID-18-API-REQUEST-DUMP` | 测试发出的真实 HTTP 请求抓包或请求体 DUMP | QA | API-DB / FULLSTACK |
| | 19 | `EVID-19-API-RESPONSE-DUMP`| 服务端返回的真实 HTTP 响应状态码与响应体 DUMP | QA | API-DB / FULLSTACK |
| | 20 | `EVID-20-DB-PERSIST-CHECK` | 直接通过 SQL 查询数据库验证数据落盘的原始记录 | QA | API-DB / FULLSTACK |
| **F. 端到端与交互验证** | 21 | `EVID-21-E2E-RUNNER-LOG` | Playwright / Cypress 执行套件完整控制台输出 | QA | FULLSTACK |
| | 22 | `EVID-22-E2E-SCREENSHOT` | 关键业务结果页面的全尺寸渲染截图（PNG 格式） | QA | FULLSTACK |
| | 23 | `EVID-23-BROWSER-CONSOLE` | 浏览器运行时控制台错误日志（必须为 0 错误） | QA | FULLSTACK |
| | 24 | `EVID-24-DOM-ASSERT-DUMP` | 页面核心 DOM 节点的选择器断言匹配证据 | QA | FULLSTACK |
| **G. 红绿变异对抗反证** | 25 | `EVID-25-RED-REPLAY-CMD` | 变异对抗回退到旧代码的执行命令 | QA | REWORK (强制) |
| | 26 | `EVID-26-RED-FAIL-STDOUT` | 确认旧代码在同一用例下确凿失败（退出码非 0）的日志 | QA | REWORK (强制) |
| | 27 | `EVID-27-GREEN-PASS-STDOUT`| 确认修复代码在同一用例下确凿通过（退出码 0）的日志 | QA | REWORK (强制) |
| | 28 | `EVID-28-MUTATION-DIFF` | 变异测试用例的设计差异比对凭据 | QA | REWORK (强制) |
| **H. 诚实申报与主锚点** | 29 | `EVID-29-NOT-RUN-LIST` | 明确未覆盖项及客观受阻原因的声明文件 | DEV / QA | ALL |
| | 30 | `EVID-30-KNOWN-RISKS` | 本切片已知缺陷或遗留边界风险记录 | DEV / QA | ALL |
| | 31 | `EVID-31-MANIFEST-ITEMS` | 包含上述执行项所有文件 SHA-256 的清册表 | QA | ALL |
| | 32 | `EVID-32-MASTER-ANCHOR` | 对 `EVID-31` 整体计算生成的 64 位 SHA-256 主锚点 | QA | ALL |

---

## 三、 主锚点本地验真命令

在 FPF 验证器中，主锚点不再是纸面文本，而是必须能被物理重算：
```bash
python -m packages.fpf_coordinator.coordinator \
  --dev-card docs/evidence/dev_handoff.yaml \
  --qa-card docs/evidence/qa_result.yaml \
  --evidence-dir docs/evidence \
  --check-git
```
若哈希不匹配或文件缺失，验证器将以退出码 1 阻断流程。
