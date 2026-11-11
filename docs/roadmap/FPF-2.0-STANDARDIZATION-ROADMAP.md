# FPF 2.0 标准化能力建设与迭代路线图

> **文档版本：** v0.2（架构规划提案；2026-11-11 基线刷新与复盘归并）  
> **编制日期：** 2026-10-31  
> **最近修订：** 2026-11-11  
> **基线：** main @ 9d96b37f10692f1108986055c0f02f161070ec4f  
> **关联工作令：** [Issue #66](https://github.com/huangzuomin/five-powers-flow/issues/66) · [PR #67](https://github.com/huangzuomin/five-powers-flow/pull/67)  
> **文档性质：** 架构规划，不替代现行 FPF-RFC-001，不构成任何代码、合并、发布或部署授权。本次修订只新增/刷新规划文本，G2–H4 的实施状态一律为 `PLAN_ONLY`。

---

## 0. 执行摘要

FPF 下一阶段的首要目标，不是继续为当前仓库增加更多 Agent、Prompt 或自动化脚本，而是把已经形成的五权治理方法、状态校验、执行隔离和证据验证能力，发展为**可复用、可移植、可验证、可持续演进的标准化工程能力**。

FPF 2.0 的目标形态是：

**一套规范标准 + 一个确定性治理内核 + 一组可插拔适配器 + 一套可移植执行运行时 + 一套证据与符合性测试体系 + 一套项目初始化和发行机制。**

它应当能够服务不同项目仓库、不同模型供应商、不同 Agent 产品、不同执行环境和不同团队，而不是依赖某一个 ChatGPT 线程、某一个 Codex 版本、某一个 GitHub 仓库或某一种本地运行方式。

FPF 的核心差异仍然是五权分立。五权是不可随意改变的治理原则；模型、Agent、代码托管平台、执行后端和工具都属于可替换的技术实现。

本路线图坚持六项原则：

1. **标准先于实现：** 先定义稳定的协议、状态语义和接口，再扩展具体工具。
2. **治理与执行分离：** Agent 可以执行任务，但不能自行授予权限、签署独立 QA 或替代人类作最终决策。
3. **内核确定性、外围可替换：** 核心状态判断和策略校验必须确定、可测试；模型和外部工具通过适配器接入。
4. **证据先于状态：** 任何状态推进都必须由可核验事实驱动，不能依赖自然语言自述或单纯的传输完成回执。
5. **最小复杂度：** 先形成可靠的单机、多项目和隔离执行能力，不提前引入不必要的分布式基础设施。
6. **符合性优先：** 新平台、新模型、新 Runner 只有通过 FPF Conformance 测试，才能声明支持 FPF。

---

## 1. 产品定位与标准化目标

### 1.1 产品定位

FPF（Five-Powers-Flow）定位为：

**面向 AI Agent 原生软件工程的可信治理与执行标准。**

它规范人类与多个 AI Agent 如何在明确权力边界、隔离执行环境和可信证据约束下，协同完成软件工程任务。

FPF 不以某个模型的智能水平作为系统可信性的基础，而是通过授权、确定性状态机、执行边界、独立验证和证据链，将模型的不确定性约束在可管理的工程流程内。

### 1.2 标准化对象

FPF 需要标准化的不是某一组 Agent Prompt，而是以下五类可交付资产：

| 标准化资产 | 主要内容 | 交付形态 |
|---|---|---|
| 规范标准 | 五权、角色、权限、任务状态、证据语义、生命周期 | RFC、规范文档、Schema |
| 参考实现 | 策略引擎、状态裁决器、协调器、Runtime、Bootstrap | Python 包、CLI |
| 适配器 | 代码托管平台、模型、Agent、Runner、工具、证据存储 | Adapter SDK、插件 |
| 符合性测试 | 协议测试、权限测试、状态机测试、证据测试、Agent Eval | Conformance Kit |
| 发行与运营 | 项目初始化、配置、升级、兼容矩阵、运行诊断 | CLI、模板、发行包、部署配置 |

### 1.3 标准不变项与可配置项

**必须保持不变的治理不变项：**

- 人类最高决策权不可由 Agent 取代。
- 代理行政权不能越权修改主干、代签 QA 或擅自部署。
- 架构规划权与业务开发执行权分离。
- 独立监察权必须具有独立身份、独立验证过程和不可被 DEV 修改的证据来源。
- 事实记账权不得代替技术裁决。
- DEV 交付、QA 通过、人类批准合并、批准部署是不同状态，不得合并为一个“完成”状态。
- 未授权、未知、证据不足或状态不一致时，默认阻断。

**允许按项目配置的实现项：**

- 模型供应商、Agent 产品及模型选择策略。
- GitHub 或其他符合性后端。
- 本地 Worktree、容器、虚拟机或托管 Runner。
- 测试 Profile、风险等级、资源配额和预算。
- 项目地图、知识库、工具清单和业务验收规则。

### 1.4 明确的非目标

FPF 不计划成为：

- 一个替代所有模型供应商的通用 Agent 平台；
- 一个替代 IDE、Git、CI/CD 或代码托管平台的产品；
- 一个只依赖 Prompt 约束角色行为的多 Agent 聊天框架；
- 一个默认获得生产权限、自动合并和自动部署的自治系统；
- 一个必须依赖 Kubernetes、复杂消息队列或中心化数据库才能运行的重型平台。

---

## 2. 当前基线与能力边界（截至 2026-11-11）

> **基线日期：** 2026-11-11（Asia/Shanghai）  
> **代码基线：** `main @ 9d96b37f10692f1108986055c0f02f161070ec4f`（本机 `git fetch origin` + `git rev-parse origin/main` 实测）  
> **证据来源：** 仓库代码与测试、`.github/workflows/`、GitHub Actions Run/Artifact、PR/Review 记录、`docs/coordination/project-map.md`、`docs/reports/FPF-AEC-DELIVERY-REPORT.md`  
> **状态口径：** `已实现` / `部分实现` / `仅文档` / `NOT_RUN`。没有固定 SHA、真实环境执行或可复核 Artifact 的项，不写作“已实现”。

### 2.1 口径纠偏：分支保护与“强制力”现状

复盘记录的原始判据是：GitHub 免费版私有仓库无法开启分支保护（`403 Upgrade to GitHub Pro`），`validate-card` 只是建议性 check，`mergeStateStatus=UNSTABLE` 仍可合并，因此宪制强制力依赖自觉。

2026-11-11 复测结果与该判据**部分不符**，必须如实拆分，不能继续沿用旧结论：

| 判据 | 2026-11-11 实测 | 结论 |
|---|---|---|
| 仓库可见性与分支保护 | `huangzuomin/five-powers-flow` 当前 `visibility=PUBLIC`；`GET /repos/.../branches/main/protection` 返回 `required_status_checks.contexts=[validate, validate-card]`、`strict=true`、`enforce_admins=true`、`allow_force_pushes=false` | 保护已真实生效；403 属私有阶段的历史约束，不再是当前事实 |
| 独立 QA 是否平台强制 | `required_approving_review_count=0`；仅 `require_code_owner_reviews=true`，而 `.github/CODEOWNERS` 指向负责人本人 `@huangzuomin` | GitHub 原生 Review 门禁**不强制**任何批准 |
| `validate-card` 强度 | `packages/fpf_policy/pr_gate.py` 对 `CODE_PR` 要求“不同 GitHub 登录身份、绑定当前 head SHA 的 APPROVED `QA_RESULT` + Artifact 校验”，失败即输出 `::error::[FPF FAIL CLOSED]` | Check 本身是 fail-closed，且在 main 上为 required；但强度完全依赖仓库内策略代码与 workflow 文件 |
| 策略自保护 | 修改 `packages/fpf_policy/`、`.github/` 或治理文件会走 `POLICY_CHANGE` / `GATE_PR`；要求第二名独立批准，但 `sovereign_override: true` 且 `sovereign_authorizer == 作者` 时可由作者本人放行（`pr_gate.py`） | 存在“作者自授权”旁路；没有平台级第二审批人，也没有密钥级身份分离 |
| 凭据分权 | 仓库内无密钥被跟踪；但本机存在未加密私钥裸放（见 G3 反例） | 未形成强制边界 |

因此 G2 的问题定义在 2026-11-11 收敛为：**check 有强制力，平台原生审批、身份分离与凭据分权没有强制力**。这不是“保护开不开”的问题，而是“谁有资格批准、凭什么批准、密钥放在哪”的问题。

### 2.2 当前 main 已具备的能力

当前 main 基线为 `9d96b37`，最近一次合并为 PR #76（AEC 地图记账）。本机 2026-11-11 运行 `python -m pytest -q`：**180 passed in 105.00s**。

| 模块 | 当前能力（实测） | 状态 | 证据 |
|---|---|---|---|
| FPF-RFC-001 | 五权治理、角色职责、交接卡、证据与生命周期规范 | 已实现（规范） | `docs/SPECIFICATION.md`，v1.2.1 |
| schemas | WORK_ORDER、DEV_HANDOFF、QA_RESULT、证据清单等结构化契约 | 已实现 | `schemas/`，`validate` workflow |
| fpf_policy | PR 角色路由、保护路径、独立 QA 证据校验与采集 | 已实现 | `packages/fpf_policy/{pr_gate,protected,qa_artifact,qa_collector}.py` |
| fpf_gates | 提测前本地门禁、DEV hook 守卫 | 已实现（本地） | `packages/fpf_gates/{pre_handoff,hook_guard_dev}.py` |
| fpf_coordinator / dispatch | 24 状态机、CAS journal、确定性归约库 | 已实现（库+测试），**未接 GitHub 事件流** | `packages/fpf_coordinator/dispatch/`，`tests/test_coordinator_kernel.py` |
| fpf_runtime / adapters | ChatGPT Web 与 Codex Worker 适配器契约、Browser Transport 抽象 | 部分实现；真实在线长会话 `NOT_RUN` | `packages/fpf_runtime/adapters/`，`tests/test_provider_adapters.py` |
| fpf_runtime / security | Credential Broker、环境净化、Windows 隔离抽象 | 部分实现；WFP 内核驱动 `NOT_RUN` | `packages/fpf_runtime/security/`，`tests/test_security_isolation.py` |
| fpf_runtime / daemon | 调度器、heartbeat、崩溃对账骨架 | 部分实现；长期跨机运行 `NOT_RUN` | `packages/fpf_runtime/daemon/`，`tests/test_daemon_reconciliation.py` |
| fpf_runtime | 单切片 DEV/QA 执行、独立 worktree、有界返工、本地 Ledger | 部分实现 | `packages/fpf_runtime/runtime.py` |
| fpf_bootstrap | 项目发现、初始化计划、工位创建、Doctor | 部分实现；main 中 `.fpf/project.yaml` 缺失 | `packages/fpf_bootstrap/`，`docs/BOOTSTRAP.md` |
| GitHub Actions | `validate`（Schema/规范/边界测试）、`validate-card`（PR fail-closed 门禁）、`fpf-independent-qa`（reviewer-dispatched，采集 Artifact） | 已实现 | `.github/workflows/` |
| AEC Phase A–G | 架构、内核、适配器、QA 证据链、安全、守护进程、Golden Path 均已合并 | 已实现（代码/文档），真实外部依赖仍 `NOT_RUN` | PR #69–#76，`docs/reports/FPF-AEC-DELIVERY-REPORT.md` |

补充说明：

- Runtime Ledger 是执行过程记录，不取代 GitHub 上的授权、PR、Review、Commit 和正式验收事实。
- 证据 Profile 已按任务类型区分，不应把“32 项证据规范”理解为每个任务机械执行全部 32 项。
- AEC 交付报告明确标注：WFP 内核驱动安装、真实 ChatGPT 在线长会话、多操作系统本地实机交叉运行均为 `NOT_RUN`，不得据文档宣称已完成。

### 2.3 已跑通但仍靠人工编排的闭环

“工单 → DEV → 固定 SHA → 独立 QA → `validate-card` → 合并 → 部署 → 地图记账”这条链路已有真实成功记录：

- **任意外部项目实证：** `huangzuomin/geo-service-core` Actions Run `42796435020`，`FPF Independent QA (reviewer-dispatched)`，`Full-Stack` profile，head `fc3e47c3f75ec649ed3b150e0d59ba94e1a15935`，2026-11-10 执行，结论 `success`。
- **本仓库实证：** PR #70–#76 每个切片均有对应 Actions Run（`41205180878`、`41218539037`、`41219858672`、`41221914610`、`41223289293`、`41225694824`）与 `fpf-qa-bot-huangzuomin[bot]` 的 APPROVED Review，合并 SHA 记录于 `docs/coordination/project-map.md`。

但这不等于“宪制强制力已落地”：

1. **状态靠人写：** `DONE / PASS / MERGED / DEPLOYED` 由协调节点或 Agent 手写进卡片、评论和地图，24 状态机库没有消费 GitHub 事件（G4）。
2. **QA 靠人触发：** `fpf-independent-qa` 是 `workflow_dispatch`，`tested_sha`、`task_id`、`profile` 由人填写；没有“PR ready 自动触发”的事件链。
3. **部署与记账靠人执行：** 部署没有容器 smoke 或迁移版本断言（H3），地图更新是独立 PR。
4. **范围靠事后再解释：** 交付范围变化没有事前 `SCOPE_AMEND`，只能在新 PR 描述里追溯（H4）。
5. **worktree 与项目边界没有生命周期：** 本机 `git worktree list` 现有 18 条记录（含主工作区），`_worktrees/` 占 0.4 GB；2026-11-10 复盘曾记录跨仓库 196 个 worktree / 19 个 dirty / 约 20–38 GB（H2）。

结论：闭环“能跑”，但“可强制、可自证、可回收”尚未成立。

### 2.4 Draft / 实验能力现状

| 事项 | 2026-11-11 实测状态 | 路线图处置 |
|---|---|---|
| Issue #61 / Draft PR #62 角色派发与恢复 | PR #62 `OPEN`、`isDraft=true`、`mergeStateStatus=DIRTY` | 纳入控制平面演进，须先解冲突、补真实 Provider Smoke 与独立 QA |
| Issue #63 / PR #64 接力演练 | PR #64 `OPEN`、`isDraft=true`、`mergeStateStatus=BEHIND` | 作为流程验证参考，不视为 Runtime 产品能力 |
| Codex Thread Bridge | 已定义可插拔 Driver 契约；真实写入/读取未验证 | 作为可选 Transport Adapter，不作为核心依赖 |
| ChatGPT Web Transport | 已定义接口与 Mock/CDP 桩；真实登录态浏览器发送、可见性、回复读取 `NOT_RUN` | 作为可选适配器，必须单独验证 |
| 有界协调循环 / daemon | 已有骨架与单测；长期运行、跨机租约未验证 | 按可靠性需求演进 |

### 2.5 尚未验证或尚未形成标准能力的事项

- 真实 Codex Desktop 线程桥的发送、回执、执行状态、结果读取和恢复。
- 真实已认证浏览器对指定 ChatGPT 会话的发送与回复核验。
- Windows 11 实机 WFP 内核驱动、完整崩溃恢复与并发验证。
- Linux 本地原生实机交叉运行（目前只有 GitHub Actions `ubuntu-latest` 远端实机）。
- 长期运行的调度器、跨机器 Runner 和可靠任务队列。
- DEV 与 QA 在操作系统账户、文件系统、凭据和网络层面的完整隔离。
- 事件驱动状态账本（G4）、项目注册表（H1）、worktree 生命周期（H2）、部署就绪门禁（H3）、范围修正协议（H4）——本路线图只给出 `PLAN_ONLY` 设计。
- 面向第三方项目的标准化安装、升级、兼容性和认证流程。
- 生产部署与真实计费调用：维持 `NOT_AUTHORIZED`，不在本路线图授权范围。

上述能力均应保持 `NOT_RUN`、`EXPERIMENTAL` 或 `PLAN_ONLY` 状态，直到有固定版本、真实环境和可复核证据。

---

## 3. FPF 2.0 目标架构

FPF 2.0 采用“规范契约为基础、五个职责平面分层、两个横向能力贯穿”的架构。

    ┌───────────────────────────────────────────────┐
    │       Protocol & Conformance Foundation       │
    │  RFC / Schema / Versioning / Conformance Kit   │
    └───────────────────────────────────────────────┘
                         │
    ┌───────────────────────────────────────────────┐
    │              Governance Plane                 │
    │ 五权、身份、授权、撤销、策略、Capability Policy │
    └───────────────────────────────────────────────┘
                         │
    ┌───────────────────────────────────────────────┐
    │                Control Plane                   │
    │ Reducer、状态机、任务队列、派发、恢复、熔断      │
    └───────────────────────────────────────────────┘
                         │
    ┌───────────────────────────────────────────────┐
    │               Execution Plane                 │
    │ Agent Session、Runner、Sandbox、Tool Gateway   │
    └───────────────────────────────────────────────┘
                         │
    ┌───────────────────────────────────────────────┐
    │             Evidence & Assurance Plane        │
    │ 证据采集、来源证明、Artifact、语义校验、独立QA   │
    └───────────────────────────────────────────────┘
                         │
    ┌───────────────────────────────────────────────┐
    │               Integration Plane               │
    │ Git Backend、Model、Agent、Runner、Tool、Storage │
    └───────────────────────────────────────────────┘

    横向贯穿：Project Context / Observability / Agent Evaluation

### 3.1 Protocol & Conformance Foundation：协议与符合性基础

定义 FPF 的公共语言和互操作契约：

- 角色、主体、权限、动作和拒绝原因。
- 任务、授权、交接、QA、证据、合并和发布的数据结构。
- 状态机、状态迁移条件和错误码。
- 事件格式、版本兼容和弃用规则。
- 适配器能力声明与符合性测试要求。

这一层属于规范，不应依赖某个模型、代码托管平台或数据库。

### 3.2 Governance Plane：治理平面

负责回答“谁在什么范围内，有权执行什么动作”。

- 人类主体和 Agent 主体的身份登记。
- 五权角色绑定和角色分离。
- Scope Grant、授权范围、有效期、撤销和再授权。
- 文件路径、工具、网络、资源、凭据和操作权限。
- 风险等级与人工审批策略。
- 统一的拒绝决策和审计记录。

权限采用默认拒绝、最小授权和短时有效原则。提示词中的角色声明不构成安全授权。

### 3.3 Control Plane：控制平面

负责回答“当前任务处于什么状态，下一步允许做什么”。

- 规范化任务状态和确定性 Reducer。
- 任务拆分、队列、派发和目标注册。
- Request ID、Attempt ID、幂等键。
- 发送回执、状态观测、超时、取消、重试和恢复。
- 事件账本、并发控制和熔断。
- 人工审批节点和人工交接。

状态决策必须由已验证的规范事实驱动。Agent 自述、Transport completed、文件存在或本地退出码，都不能单独构成正式 QA PASS 或合并授权。

### 3.4 Execution Plane：执行平面

负责实际执行任务，但不拥有治理裁决权。

- Agent Session：创建、恢复、取消和读取模型会话。
- Runner：为任务分配工作区、进程和运行资源。
- Sandbox：文件系统、进程、网络和凭据隔离。
- Tool Gateway：所有工具调用的统一授权入口。
- Credential Broker：向任务提供最小范围、短时有效的凭据。
- Resource Budget：限制时间、Token、并发、CPU、内存和费用。

### 3.5 Evidence & Assurance Plane：证据与保证平面

负责回答“执行了什么、谁执行的、针对哪个版本、凭什么认定结果成立”。

- Evidence Collector：采集原始日志、测试输出和环境信息。
- Evidence Store：独立保存证据制品，支持内容寻址和完整性校验。
- Provenance：记录主体、Runner、工具链、环境和执行来源。
- Evidence Verifier：校验结构、哈希、来源、语义和覆盖范围。
- Independent QA：独立身份、独立环境和独立验收。
- Assurance Report：输出 PASS、FAIL、BLOCKED、INVALID_TEST 及未覆盖风险。

### 3.6 Integration Plane：集成平面

通过稳定适配器接入外部生态：

- Governance Backend：GitHub 为第一参考实现，后续可评估 GitLab 等后端。
- Model Provider：OpenAI、Anthropic及其他兼容模型供应商。
- Agent Adapter：Codex CLI、Agents SDK 及其他 Agent 执行产品。
- Runner Backend：Local Worktree、Docker、Ephemeral VM、托管 Runner。
- Tool Adapter：Git、Shell、浏览器、数据库、API、监控等。
- Evidence Storage：本地、GitHub Actions Artifact、对象存储等。

适配器必须声明能力、权限、版本和限制。没有真实接口的能力必须返回 NOT_SUPPORTED、BLOCKED 或 NOT_RUN，不得用模拟结果伪装成功。

### 3.7 横向能力

**Project Context：** 将项目地图、规范、架构、知识库、历史决策和错题本编译成任务级 Context Pack。Context 是可更新的项目输入，不是高于授权和事实记录的第二套权威账本。

**Observability & Agent Evaluation：** 统一采集任务、模型、工具、Runner、证据和成本轨迹；持续测试 Agent 是否理解项目、遵循协议和正确拒绝越权。

---

## 4. 核心模块边界与现有代码映射

不建议现在立即大规模重命名 Python 包。先稳定职责和接口，再通过兼容层逐步调整目录。

| 目标能力 | 当前代码承载 | 2.0演进方向 |
|---|---|---|
| Protocol / Schema | docs/SPECIFICATION.md、schemas/ | 独立版本化，成为规范契约 |
| Governance Policy | packages/fpf_policy/ | 统一主体、角色、授权和能力策略 |
| Local Gates | packages/fpf_gates/ | 保留本地快速拦截，策略与服务端保持一致 |
| State Reducer / Validation | packages/fpf_coordinator/ | 抽离纯函数状态裁决和后端读取接口 |
| Dispatch / Reconciliation | PR #62 的 dispatch 实验实现 | 经审查后纳入 Control Plane，避免重复状态机 |
| Execution Runtime | packages/fpf_runtime/ | 统一 Agent Session、Runner、Sandbox 和生命周期 |
| Bootstrap | packages/fpf_bootstrap/ | 项目初始化、配置校验、升级和兼容迁移 |
| Evidence | coordinator、qa_collector、GitHub Actions | 统一 Evidence Envelope、Store 和 Verifier |
| Adapters | 当前分散在 Runtime / Coordinator | 建立独立适配器契约和注册机制 |
| Conformance / Agent Eval | 当前测试与边界测试 | 建立独立、可发行的符合性工具包 |

### 4.1 状态账本与权威事实必须分开：对账与恢复协议（Reconciliation Protocol）

Runtime Ledger 与 PR #62 中的 Dispatch Journal 不应简单合并，也不能各自演化成独立的权威状态源。

统一原则：

- GitHub 参考后端中的 Issue、PR、Review、Commit、Workflow 和 Artifact，承载该后端配置下的正式治理事实。
- Git Commit SHA 锚定代码物理版本。
- 经验证的 Artifact 和 QA Review 锚定独立验收事实。
- SQLite 等本地 Ledger 只记录执行意图、回执、轮询、重试和恢复过程。
- 本地账本丢失或与远端事实冲突时，必须重新读取权威后端并执行正式的**对账与恢复协议（Reconciliation Protocol）**，不能凭本地状态推进正式生命周期。

2.0 将 **对账与恢复（Reconciliation）** 从单一模块名称提升为**系统级核心治理协议（Reconciliation Protocol）**。在分布式或跨进程执行中，重新读取远端并不天然等同于知晓下一步动作（例如外部 Provider 副作用未收到回执时进程崩溃，盲目重发将导致重复执行，盲目判负将导致孤儿任务）。

#### 1. Reconciliation 两层状态机与远端执行子状态（F-03）

为消除状态语义混淆，系统确立**两层状态映射架构**：第一层为控制平面的**对账决水状态（Reconciliation State）**，第二层为外部实体的**远端执行子状态（Remote Execution Sub-State）**。调度器必须根据精准的执行子状态决定后续调度动作：

| 对账决水状态 | 映射远端执行子状态 | 判定语义 | 严格限定的系统调度动作 |
|---|---|---|---|
| `REMOTE_CONFIRMED` | `REMOTE_ACCEPTED` | 权威远端已安全持久化接收任务，正排队待分配 | 记录远端任务 ID 与回执，**进入只读定时轮询**，禁止重新派发 |
| `REMOTE_CONFIRMED` | `REMOTE_RUNNING` | 权威远端确认任务正在活跃执行中 | **恢复外部进度观测与事件监听**，**严禁再次发起任务派发（防并发冲突）** |
| `REMOTE_CONFIRMED` | `REMOTE_SUCCEEDED` | 权威远端确认执行已圆满完成，终态产物已就绪 | 触发证据引擎拉取远端制品并核验哈希，平滑推进至下一治理阶段 |
| `REMOTE_CONFIRMED` | `REMOTE_FAILED` | 权威远端确认执行失败（异常退出或断言失败） | 拉取失败诊断包与完整日志，判定返工预算，触发受控有界返工 |
| `REMOTE_CONFIRMED` | `REMOTE_CANCELLED` | 权威远端确认执行已响应取消指令并终止 | 回收本地工作区与临时凭据，将任务归档为撤销终态 |
| `LOCAL_PENDING` | `REMOTE_UNSEEN` | 本地已记录执行意图，远端尚未确认但仍处于可见性窗口内 | 维持当前状态，继续执行只读幂等核验探针，禁止推进业务状态 |
| `UNKNOWN_OUTCOME` | `REMOTE_UNKNOWN` | 外部副作用发送结果未知（已发出未回执/网络中断/进程崩溃） | **严禁盲目重发**；保持当前任务阻断，启动只读退避探针核实外部真实状态 |
| `REMOTE_CONFLICT` | `STATE_DIVERGED` | 本地记录与权威远端事实冲突（如未授权 SHA 漂移或跨分支篡改） | 立即暂停推进，触发高危告警并冻结工单，禁止自动重试 |
| `REMOTE_UNAVAILABLE` | `BACKEND_OFFLINE` | 权威治理后端（如 GitHub API）网络离线或鉴权失效 | 系统 Fail-Closed 阻断，保持本地意图只读，等待连通性恢复 |
| `HUMAN_RESOLUTION_REQUIRED` | `ESCALATED_TO_HUMAN` | 存在不可逆状态分歧、探针超时或自动决水不可达 | 终止自动重试，持久化分歧证据包，在治理状态机中升级人类负责人手工裁定 |

#### 2. Agent Provider 幂等能力三级分级模型与硬性防重约束（F-01 & F-02）

由于外部大模型 Provider 与执行引擎的实现差异，系统不得假设所有 Provider 均具备原生幂等性，必须按能力分级施加恢复策略：

| 能力等级 | Provider 特征 | 适用系统恢复策略与硬性防重约束 |
|---|---|---|
| **Class A（原生幂等）** | 原生支持 `idempotency_key` 过滤 | 允许自动重发，但**必须同时满足以下硬性契约（F-01）**：<br>1. **三要素严格匹配**：重发必须使用原始 `idempotency_key`；请求体规范化摘要 `canonical_payload_digest` 必须 100% 严格一致（Key 相同但 Payload 改变时 Provider 必须抛出 `IDEMPOTENCY_CONFLICT` 拒绝）；处于 Provider 声明的有效保留期（Retention Period）内。<br>2. **显式幂等作用域（Idempotency Scope）**：Provider 必须显式声明 Key 的唯一性作用域（如 `Tenant` 租户级、`Endpoint` 路由级、`Session` 会话级或 `Workspace` 工作区级），禁止跨作用域冲突误判。<br>3. **并发请求去重语义（Concurrent Deduplication）**：当两个携带相同 Key 的请求并发到达时，Provider 必须原子互斥锁定，**保证只创建一个逻辑执行实例**，并发调用者挂起等待同一执行实例生成回执或订阅同一结果，严禁并发穿透。<br>4. **保留期起算点权威定义（Retention Semantics）**：Retention Period 必须以 Provider 正式生成并持久化首次回执的时间戳（Receipt Timestamp）为基准起算，禁止客户端主观猜测。 |
| **Class B（可查不可防重）** | 不支持请求去重，但提供任务查询接口（可查 Request ID 历史） | **硬性安全铁律**：**无法证明远端绝对未执行，就绝对不能把未发现远端记录（`NOT_FOUND`）当作未执行；严禁为了提高自动化率牺牲外部副作用安全性！**（C-01 & F-02）<br>受网络单向延迟与最终一致性影响，仅凭客户端 `sent_at` 与查询接口返回 `NOT_FOUND` **仍不足以证明远端绝对未接收执行**（请求可能因网络延迟滞留于链路中，导致后续重发引发双实例冲突）。因此，**只有当 Provider 同时满足以下三项强保证时，才允许在探针期满后自动重发**：<br>1. **权威接收时间界限与单向延迟保证**：Provider 具备权威时间戳同步机制，并能给出严格的接收延迟上限保障；<br>2. **查询接口强一致性 SLA 与可见性窗口**：Provider 承诺可见性延迟窗口（Visibility Delay Window，如 30s）后，历史记录查询具有强一致性（Strong Consistency / Read-After-Write SLA）；<br>3. **迟到请求防护与丢弃机制（Late-Arriving Request Drop Mechanism）**：Provider 服务端具备基于请求时间戳或有效期的迟到请求自动丢弃能力（例如请求头携带 `X-Request-Expires-At`，若请求因网络延迟到达超过有效期，Provider 拒绝执行而不是创建新任务）。<br>**降级规则**：凡 Provider **不能提供上述完整接收界限与迟到防护保证者，一律严禁自动重发**；多次查询返回 `NOT_FOUND` 时一律强制降级为 `UNKNOWN_OUTCOME`，终止自动调度，持久化现场证据并升级至 `HUMAN_RESOLUTION_REQUIRED` 由人工核验！ |
| **Class C（无查询无幂等）** | 既不支持去重也不提供可信执行历史查询接口 | 发生未知中断时一律强制置为 `UNKNOWN_OUTCOME`，**绝对禁止自动重发**，仅允许保存现场证据并直接升级人类接入。 |

#### 3. 探针恢复算法与超时退避预算（Probe Recovery Algorithm）

针对 `UNKNOWN_OUTCOME` 状态，控制平面必须启动受限只读探针：
- **只读零副作用契约**：探针仅调用只读查询接口（如 `check_status`、`query_request_receipt`），严禁触发任何产生新任务的写操作。
- **指数退避与抖动预算**：探测间隔按 2s、4s、8s、16s 指数退避并加入随机抖动（Jitter，±20%），最大单次请求超时 5s，总探测超时预算硬性设定为 60 秒。
- **探针预算与可见性窗口协同**：60 秒探针总超时预算必须严格大于 Provider 声明的最大可见性延迟窗口（如 30 秒），最后一次探针尝试的截止时间必须落在可见性窗口之外，确保判定安全性。
- **决水与超时升级（C-01 严格受限重发契约）**：
  - 若在预算时间内探针核实任务已成功接收并生成回执，状态平滑跃迁至 `REMOTE_CONFIRMED` 并按远端执行子状态推进（`REMOTE_ACCEPTED` 等待轮询，`REMOTE_RUNNING` 恢复观测）；
  - 若探针核实任务未被接收，**仅在 Provider 具备 Class A 原生幂等或具备 Class B 权威接收界限与迟到防护保证时**，方可将状态置为 `LOCAL_PENDING` 并安全重新派发；
  - 若为普通 Class B/Class C Provider 或超过 60 秒依然无法排除迟到与执行未知，立即强制跃迁至 `HUMAN_RESOLUTION_REQUIRED`，冻结任务推进，杜绝无限悬挂与双写副作用。

#### 4. 细化权威字段映射与版本合法性校验

- **授权返工 vs 非法 Commit 漂移**：
  - 合法返工：必须由独立 QA 的 `QA_FAILED` 或人类明确指令触发，并绑定有效 WORK_ORDER 生成前置因果事件，此时产生的新 Commit SHA 属于合法候选版本；
  - 非法漂移：若在未触发返工、缺少前置事件或未授权分支上检测到 PR Head SHA 变更，纯函数 Reducer 立即判定为 `REMOTE_CONFLICT` 并阻断合流。
- **QA Review 严格绑定具体 SHA**：
  - 独立平台 `APPROVED` Review 必须严格校验 `review.commit_id == pr.head_sha`；任何针对历史 Commit 的过时 Review 或泛化 PR 审批在最新 Head SHA 上一律视为无效，必须 Fail-Closed 阻断。
- **非事务边界与归约保障**：
  - 明确 GitHub 的多对象（Issue/PR/Review/Workflow）并非天然强一致事务数据库，所有跨对象状态归约必须由纯函数 Reducer 确定性判定，无法决水时严格停机并请求人类介入。

2.0 应统一 Task ID、Request ID、Attempt ID、Event ID、Correlation ID、Causation ID 和事件格式，但暂不要求统一底层数据库。只有在多 Runner、多实例和并发需求得到实测后，再决定是否引入 PostgreSQL 或消息队列。

### 4.2 GitHub 中立化与兼容策略

现行 RFC-001 的 GitHub Profile 继续以 GitHub 作为正式治理记录和存证总线。2.0 的核心内核不应直接依赖 GitHub API 的具体字段和调用方式。

通过 Governance Backend 接口隔离平台差异。GitHub Adapter 是第一个标准参考实现；其他平台只有在能够提供等价的身份认证、授权、版本锚定、审查、制品和审计能力，并通过 Conformance 测试后，才能声明 FPF 兼容。

这不是取消 GitHub 的现行权威地位，而是把 GitHub 的实现事实与 FPF 的通用规范分开。

---

## 5. 核心数据契约与事件模型

FPF 2.0 至少应统一以下规范对象：

| 契约 | 主要职责 |
|---|---|
| Project Manifest | 项目标识、规范版本、后端、适配器和策略配置 |
| Principal / Role Binding | 人类、Agent、服务主体及其角色绑定 |
| Capability Profile | 可执行动作、路径、工具、网络和资源范围 |
| Work Order | 任务目标、验收条件、允许路径和停止条件 |
| Scope Grant / Revocation | 授权、范围绑定、撤销和再授权 |
| Task Event | 任务生命周期中的规范化事件 |
| Dispatch Request / Receipt | 派发意图、目标、回执和幂等信息 |
| Execution Envelope | Agent、Runner、环境、工具调用和执行结果 |
| DEV Handoff | 开发交付、代码 SHA、自测和未验证项 |
| QA Result | 独立验收主体、固定 SHA、结论和下一动作 |
| Evidence Manifest / Attestation | 证据清单、来源、哈希和验证声明 |
| Merge / Release Record | 人类批准、合并版本和发布记录 |
| Context Pack | 任务执行所需的项目规范和知识快照 |

### 5.1 统一事件信封、Transactional Outbox 与回放副作用物理隔离

建议所有跨模块事件采用包含严格因果关系、事务发件箱与回放隔离语义的公共信封契约：

- `event_id`：全局唯一事件标识。采用 UUIDv7 生成，具备**局部时间排序特征**，但**不代表全局严格单调递增**。全局严格逻辑顺序由权威存储分配的 `sequence` 保证。
- `event_schema_version`：事件信封与载荷的契约版本，支持跨版本向后兼容。
- `aggregate_id`：事件所属的业务聚合根标识（如 `task_id`、`session_id`）。
- `aggregate_version`：聚合版本号，单调递增整型，用于支撑原子 CAS 写入控制。
- `causation_id`：直接引发本事件的前置事件 ID 或命令 Request ID，构成因果溯源链。
- `correlation_id`：贯穿整个端到端业务生命周期的追踪链标识（如 `workflow_run_id`）。
- `recorded_at`：权威事件存储确认落盘的物理服务端时间戳（UTC）。
- `occurred_at`：事件在适配器或客户端实际发生的观察时间戳（UTC）。
- `sequence`：事件流中的逻辑严格自增序号，由本地数据库在原子事务中分配。
- `topic`：业务事件类型命名空间，如 `fpf.lifecycle.dispatched`。
- `actor`：事件发起主体标识，必须区分为 `HUMAN_OPERATOR`、`DEV_AGENT` 或 `QA_AGENT`。
- `source_adapter`：事件来源适配器及环境标识。
- `object_refs`：Commit SHA、PR Number、Workflow Run ID、Artifact SHA 等外部权威引用。
- `payload_digest`：事件载荷的 SHA-256 哈希摘要，保障事件防篡改。
- `replay_policy`：事件回放策略枚举（`PROJECTION_ONLY` 为强制默认策略，运行时物理阻断外部副作用）。

#### 原生条件更新 CAS 与 Transactional Outbox 事务契约（F-06 & C-02）

为彻底消除“数据库版本已提交但事件发布失败导致下游丢事件”或“普通并发读取导致状态覆盖”的双写与竞态故障窗口，事件引擎必须实现基于原生条件更新与确定性 sequence 分配的 Transactional Outbox 契约：

```sql
BEGIN TRANSACTION;
  -- 1. 原生原子条件更新（Atomic Conditional Update，消除 SELECT 与 UPDATE 竞态窗口）
  UPDATE task_aggregates
  SET aggregate_version = aggregate_version + 1,
      updated_at = :current_timestamp
  WHERE aggregate_id = :agg_id
    AND aggregate_version = :expected_version;

  -- 检查受影响行数恰好为 1，若为 0 说明发生并发版本冲突，立即回滚并转入 Reconciliation
  IF rows_affected != 1 THEN
    ROLLBACK;
    RAISE CONCURRENCY_CONFLICT;
  END IF;

  -- 2. 确定性序号分配与不可变事件流水写入（C-02 核心契约）
  -- 序号分配原则：直接使用成功 CAS 递增后的聚合版本作为事件序号（sequence = expected_version + 1 = aggregate_version）
  -- 表级约束：对 (aggregate_id, sequence) 建立 UNIQUE 联合唯一约束；对 event_id 建立全局 UNIQUE 唯一约束
  INSERT INTO task_events (
    event_id, aggregate_id, aggregate_version, sequence,
    topic, actor, payload, payload_digest, causation_id, correlation_id, recorded_at, replay_policy
  ) VALUES (
    :event_id, :agg_id, :expected_version + 1, :expected_version + 1,
    :topic, :actor, :payload, :payload_digest, :causation_id, :correlation_id, :current_timestamp, 'PROJECTION_ONLY'
  );

  -- 3. 同一事务中写入 Outbox 发件箱表（status 默认为 'PENDING'）
  INSERT INTO transactional_outbox (outbox_id, event_id, destination, status, created_at)
  VALUES (:outbox_id, :event_id, :destination, 'PENDING', :current_timestamp);
COMMIT;

-- 4. 异步 Outbox Dispatcher 守护进程
Outbox Dispatcher 独立轮询或监听 Outbox 表 ──> 保证 At-Least-Once 投递至事件总线
       ↓
投递成功收到总线 ACK ──> 更新 Outbox 表 status = 'SENT'（独立于下游消费确认）

-- 5. 下游订阅者独立 Inbox 幂等消费契约（C-02 本地事务与唯一约束）
-- consumer_inbox 表定义：PRIMARY KEY (consumer_name, event_id)
-- 消费端必须将“业务投影写入”与“插入 consumer_inbox”置于同一个本地数据库事务中；
-- 严禁将 SELECT EXISTS 充当并发排他锁，直接依赖主键唯一约束原子排他：
BEGIN TRANSACTION;
  SAVEPOINT before_consumption;
  -- 尝试原子插入消费凭据（若并发消费者同时处理，由数据库内核级唯一约束排他拦截）
  INSERT INTO consumer_inbox (consumer_name, event_id, processed_at)
  VALUES (:c_name, :e_id, :current_timestamp);

  -- 插入成功说明该消费者首次处理该事件，原子执行业务投影更新
  UPDATE task_projections SET ... WHERE ...;
  RELEASE SAVEPOINT before_consumption;
  COMMIT;
EXCEPTION WHEN UNIQUE_VIOLATION THEN
  -- 捕获到唯一键冲突，说明并发消费者已抢先处理或此前已完成消费
  ROLLBACK TO SAVEPOINT before_consumption;
  COMMIT; -- 回滚业务投影，直接向总线返回幂等 ACK，避免重复执行副作用
```

**关键架构隔离铁律**：
1. **Outbox 与 Inbox 严格分权**：Outbox 发送确认只代表 Dispatcher 投递完成；下游消费者维护独立的 `consumer_inbox` 幂等消费表，二者逻辑与物理账本严格分离。
2. **内部可靠投递 vs 外部副作用**：Transactional Outbox 仅保障系统内部事件的**可靠投递与内部最终一致性**；外部大模型或三方 API 的外部副作用无法纳入数据库事务，必须由对账协议（Reconciliation Protocol）与 Provider 幂等契约（Class A/B）在应用层共同治理，两层绝不混淆。

#### 事件回放（Event Replay）与外部副作用绝对物理隔离铁律

必须严格区分**事件回放（Event Replay）**与**命令重执行（Command Re-execution）**：
1. **事件回放（Event Replay）**：仅用于系统冷启动、灾备重建、内存投影更新或本地审查。回放期间的 `replay_policy` 必须为 `PROJECTION_ONLY`。在运行时层面，依赖注入容器必须**将底层的 Tool Gateway、网络客户端和 Agent Provider 强制替换为 NullMock 或 DisabledClient**，**绝对禁止产生任何外部网络请求、写操作或模型调用**。
2. **命令重执行（Command Re-execution）**：若需重新执行某项业务动作，必须生成全新的命令意图（包含全新的 `request_id` 与递增的 `attempt_id`），重新走五权授权、参数校验与幂等派发通道，绝不允许假借“回放历史事件”名义隐式重发请求。

事件记录应追加写入，禁止用后续状态覆盖历史事实。状态是对经过验证事件流的确定性归约结果，而不是 Agent 自由填写的字段。

### 5.2 授权版本绑定

授权必须绑定不可歧义的工作令内容摘要、基线 SHA、项目、任务、目标分支、授权主体和重试上限。

授权修订应使用内容寻址或明确的不可变版本标识。不得简单依赖会被评论、通知等附属操作改变的可变更新时间字段，否则可能产生授权版本与平台更新时间之间的循环失配。

撤销必须形成独立、可核验事件；权限丢失、工作令内容变化、基线变化或范围变化均应触发阻断或重新授权。

---

## 6. 适配器与执行接口标准

FPF 2.0 不要求所有外部系统采用相同技术栈，但要求它们遵守相同的接口语义。

| 接口 | 最小职责 | 关键约束 |
|---|---|---|
| GovernanceBackend | 读取任务、授权、Review、Commit、Workflow 和 Artifact | 返回可验证主体与版本，不得仅信任自由文本 |
| AgentProvider | 创建会话、提交任务、读取状态、取消和获取输出 | 明确模型、版本、会话身份和能力限制 |
| ExecutionBackend | 创建、执行、收集、恢复和销毁环境 | 环境隔离、资源限制、生命周期可恢复 |
| ToolGateway | 发现工具、授权、调用、审计 | 每次调用执行策略检查 |
| CredentialProvider | 发放和撤销短时凭据 | 最小权限、短时有效、禁止泄露到日志和证据 |
| EvidenceStore | 保存、读取和校验制品 | 内容摘要、权限隔离、保留策略 |
| EvidenceVerifier | 验证证据结构、来源、语义和覆盖 | 缺失、未知、过期或不一致时 Fail Closed |
| ContextProvider | 生成任务级 Context Pack | 绑定项目版本、来源和更新时间 |

### 6.1 三层执行后端架构与 Windows 11 原生安全隔离契约

FPF 的核心目标是统一治理协议，而不是强制所有执行环境采用单一技术实现。FPF 主研发机与开发者工作站广泛运行在 Windows 11 原生环境，涉及 Windows 专有工具链、NTFS 权限及本地桌面交互。追求架构规范绝不能以牺牲 Windows 11 原生环境的实际可用性为代价。同时，原生兼容性必须建立在严谨的受控威胁模型与严格安全契约之上，杜绝虚假的安全绝对化承诺。

2.0 确立**三层执行后端架构（Three-Tier Execution Architecture）**：

1. **第一层：Local Worktree Runtime（Windows 11 原生生产级一级支持后端）**
   - **定位**：面向宿主机本地工具链、Windows 专有软件依赖及高频交互式研发的标准原生兼容后端。
   - **安全边界声明**：属于原生可执行环境，必须施加操作系统级受控防护契约，不宣称为不可破的沙箱。
2. **第二层：Docker Sandbox Runtime（标准隔离执行后端）**
   - **定位**：面向 Linux 容器化、跨平台测试、网络隔离与干净构建环境的标准化隔离后端，优先建设。
3. **第三层：Ephemeral VM Runtime（高风险强隔离后端）**
   - **定位**：面向不可信第三方代码、系统内核级修改或高危自动化操作的强安全后端，后续按需引入。

#### Windows 11 原生环境受控威胁模型与硬性安全契约（F-04 & F-05）

针对宿主机同用户执行可能导致的权限混淆、凭据泄露及进程残留风险，Windows Local Worktree 必须执行以下受控契约：

1. **操作系统级身份隔离（OS Identity Separation）**：
   - 生产环境中，DEV Agent 与 QA Agent 必须运行在独立的非管理员 Windows 用户账户下（如 `fpf_dev_worker` 与 `fpf_qa_worker`）；
   - 禁止在特权管理员（Elevated Admin / UAC bypass）上下文运行 Agent 进程。
2. **源码只读 ACL 与外部证据存储（Read-Only ACL & External Storage）**：
   - 在 QA 任务启动时，系统通过 Windows NTFS ACL（如 `icacls`）将 DEV 工作树目录对 QA 账户显式标记为**严格只读（Read & Execute only）**，物理阻断 QA 修改被测代码的可能；
   - **外部证据存储契约**：QA 的测试产物与审计日志**强制重定向至工作区外独立的受保护凭据存储卷**，DEV 账户对此目录无修改权限，严禁 QA 在被测仓库工作树内直接获得写入权限。
3. **Credential Broker 认证代理与安全生命周期（F-05 & C-04）**：
   - **IPC 客户端身份认证与宿主预期四元组严格对账**：Credential Broker 仅通过本地命名管道（Named Pipe）提供临时凭据服务；管道配置严密安全描述符（SDDL）。宿主超级守护进程在派发 Worker 进程时，必须在 Broker 权威授权注册表中预先登记合法的执行四元组：`(expected_pid, expected_creation_time, task_id, job_handle)`；
   - **防 PID 回收重用与创建时间核验**：Broker 收到连接时，调用 `GetNamedPipeClientProcessId` 取得客户端 PID 后，必须通过 `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` 获取进程句柄，调用 `GetProcessTimes` 读取实际创建时间戳 `actual_creation_time`，并与宿主预先登记的时间戳进行严格双向比对：`actual_pid == expected_pid AND actual_creation_time == expected_creation_time`。若时间戳失配或进程已被替换，立即拒绝连接，彻底杜绝 PID 回收重用攻击；
   - **Job Object 归属核验**：通过 `IsProcessInJob` 严格校验该进程句柄确实隶属于宿主为当前任务派发且在注册表中绑定的 `job_handle` 实例；
   - **细粒度任务级授权绑定（Task-Bound Scope Grant）**：请求载荷中的 Task ID 必须与注册表中该进程绑定的 `task_id` 100% 严格一致，严禁跨任务冒用；进一步核验 Audience、具体 API Scope、任务生命周期状态以及当前撤销版本（Revocation Version）；
   - **模拟失败即时 Fail-Closed 与 RevertToSelf**：调用 `ImpersonateNamedPipeClient` 执行安全上下文模拟；**若身份模拟失败（返回值 FALSE），服务端绝对禁止以 Broker 自身高权限继续执行后续请求**，必须立即 Fail-Closed 抛出安全异常并断开管道；在模拟检查完成后及任何退出分支，必须强制调用 `RevertToSelf` 恢复自身安全上下文，杜绝特权残留；
   - **短期作用域令牌与内存清零**：Agent 进程严禁持有长期持久化密钥（如 GitHub PAT），仅由 Broker 按任务签发限定 Audience、限定 Scope、最短生存期（TTL ≤ 15 分钟）的临时令牌；任务撤销（`REVOKED`）或超时时 Broker 立即远程吊销并在本地失效；固定缓冲区使用后调用 `SecureZeroMemory`；
   - **Broker 反向代理与操作级审计优先原则**：对于 GitHub API、远端制品存储上传等标准外部调用，优先由 Broker 作为受保护的反向代理直接代为发起调用，不仅验证连接发起者，更对发出的每个具体 HTTP/API 操作进行白名单路径、动作与参数级深度审计，仅将结果返回给 Agent，最大程度避免凭据实体暴露于 Worker 内存空间；
   - **非标准进程创建逃逸测试**：Job Object 默认管理通过 `CreateProcess` 创建的子进程，但通过 WMI（`Win32_Process.Create`）或 RPC 机制发起的跨上下文进程创建无法自动继承 Job 关联，必须在安全策略中审计并禁止 Worker 调用此类接口，并将其列入 Conformance 专用逃逸测试。
4. **Windows Job Objects 进程树回收与启动安全序（F-04）**：
   - **消除绝对化承诺**：在受支持的 Windows 环境及既定威胁模型下，通过 Windows Job Objects 施加严格的进程生命周期管理；
   - **挂起启动与入组失败硬防护**：宿主使用 `CREATE_SUSPENDED` 标志调用 `CreateProcess` 创建初始进程，并立即调用 `AssignProcessToJobObject`；**若绑定失败，宿主必须立即调用 `TerminateProcess` 强制销毁进程并拒绝启动，严禁在未成功加入 Job Object 前调用 `ResumeThread`**，彻底消除加入前的逃逸竞态；
   - **句柄权属与防跨进程复制**：Job Handle 仅由宿主超级守护进程持有，设置 `bInheritHandle = FALSE`，并通过安全描述符禁止子进程复制或打开 Job 句柄；显式配置 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`，且不授予 `JOB_OBJECT_LIMIT_BREAKAWAY_OK` 策略，从内核层拦截 `CREATE_BREAKAWAY_FROM_JOB`；
   - **嵌套与终止验证**：支持 Windows 嵌套 Job 策略，确保终止信号逐级传递；该机制必须通过 Conformance Suite 中的专用进程树逃逸测试验证。
5. **Windows 过滤平台（WFP / ALE）网络出站分层隔离契约（F-04 & C-03）**：
   - **区分全局配置与内核过滤层**：标准 Windows 高级防火墙的 `DefaultOutboundAction` 属于设备/网络配置文件（Domain/Private/Public）全局策略，默认通常为 Allow，无法单凭普通防火墙规则直接为特定本地用户设定独立的默认出站动作；
   - **严格限定 ALE 层用户身份过滤条件**：
     1) **ALE 连接授权层（`FWPM_LAYER_ALE_AUTH_CONNECT_V4` 与 `FWPM_LAYER_ALE_AUTH_CONNECT_V6`）**：在此层依据 Worker 账户的用户安全标识符（User SID，如 `fpf_dev_worker` 与 `fpf_qa_worker`）精确配置 `FWPM_CONDITION_ALE_USER_ID` 过滤规则。对命中该 SID 的所有出站 TCP 握手、UDP 首次发包以及 Raw Socket/ICMP 会话建立实施默认丢弃（Block / Drop），仅精确白名单放行目标为本地 Tool Gateway（限定本地 IPv4 `127.0.0.1`、指定监听端口 `49152`，并绑定 Tool Gateway 宿主应用二进制路径哈希）的合法 TCP 连接；
     2) **ALE 资源分配层（`FWPM_LAYER_ALE_RESOURCE_ASSIGNMENT_V4` 与 `_V6`）**：依据 Worker SID 实施本地 Socket 绑定与监听控制，严格禁止 Worker 进程在未授权端口上创建对外监听端点；
     3) **传输层原生过滤与流上下文层级归属约束（Transport Layers & Explicit Flow Context Constraints）**：明确 `FWPM_CONDITION_ALE_USER_ID` 仅用于原生支持该身份条件的 ALE 过滤层，严禁在 `OUTBOUND_TRANSPORT` 层直接使用该身份条件。传输层（`FWPM_LAYER_OUTBOUND_TRANSPORT_V4` 与 `_V6`）仅依据该层原生支持的过滤条件（如 `FWPM_CONDITION_IP_PROTOCOL`、`FWPM_CONDITION_IP_REMOTE_ADDRESS`、`FWPM_CONDITION_IP_REMOTE_PORT`）实施逐包过滤。明确 `FwpsFlowAssociateContext0` 只能由内核 Callout Driver 用于 WFP 中支持数据流上下文关联的目标过滤层（如 `FWPM_LAYER_STREAM_V4/_V6`、`FWPM_LAYER_DATAGRAM_DATA_V4/_V6` 或 `FWPM_LAYER_ALE_FLOW_ESTABLISHED_V4/_V6`）及其注册的 Callout，上下文仅供对应 Callout 在 `classifyFn` 中接收，绝对不自动跨层传播至 `OUTBOUND_TRANSPORT` 等数据包过滤层；严禁假定 `OUTBOUND_TRANSPORT` 层能自动获得 Flow Context。若未来需要在传输层依据 Worker 身份实施过滤，必须另行设计并实机验证专属的身份关联机制；流终止时由 Filter Engine 通知并由对应 Callout 注册的 `flowDeleteFn` 释放上下文；所有未经真实内核驱动实现与 Windows 11 实机验证的能力，一律严格标记为 `NOT_RUN`。
   - **分协议覆盖与未经实测声明约束**：
     - TCP/UDP：通过 ALE 连接授权层实现基于 Worker SID 的严格拦截与本地白名单放行；
     - IPv6：默认在 `_V6` ALE 过滤层施加丢弃规则，物理阻断 IPv6 回环地址（`::1`）与外网探测；
     - ICMP / Raw Sockets：在 ALE 层拦截其 Socket 创建与连接建立；
     - **真实边界声明**：以上为 Windows 原生环境下的设计安全契约与架构规程；未经真实 Windows 11 实机与专用安全套件验证的能力，严格标记为 `NOT_RUN`，严禁在文档中提前宣称已实现生产级 100% 物理阻断，待阶段 3 实机落地时通过专用 Conformance 网络渗透用例验证。
6. **Tool Gateway 全面接管（Tool Gateway Interception）**：
   - 严禁 Agent 自由调用未经白名单审计的 Windows 系统命令或自动化浏览器；所有文件写操作、网络请求与外部工具调用统一经由 Tool Gateway 策略引擎鉴权。

#### Windows 11 与 Linux (Ubuntu) 跨平台支持矩阵

| 验证维度 | Windows 11 (原生环境) | Linux (Ubuntu / Docker) | 核心跨平台一致性要求 |
|---|---|---|---|
| **Local Worktree** | 生产级实测（一级支持后端） | 生产级实测（一级支持后端） | 保证两端命令规范、参数解析与状态归约完全一致 |
| **Docker Sandbox** | 生产级实测（WSL2 引擎 / Docker Desktop） | 生产级实测（原生 Docker Engine） | 规范 Linux 容器与 Windows 宿主机之间的路径映射与权限转换 |
| **文件系统与路径** | 兼容大小写不敏感、反斜杠/正斜杠兼容、NTFS 权限 | 大小写敏感、POSIX 权限模型、符号链接 | 核心协议内部全部使用规范化正斜杠 UTF-8 相对路径 |
| **进程与生命周期** | Windows Job Objects 挂起启动绑定与严格回收 | POSIX 进程组与 cgroups 资源回收 | 超时或取消时必须保证子进程树被完全清理 |
| **凭据与环境变量** | Broker 短期令牌 + Named Pipe ACL 认证 + 内存清零 | POSIX 环境变量与临时 tmpfs 挂载 | 无论平台，敏感 Token 与私钥一律禁止落盘到被测目录 |
| **网络边界防护** | Windows 本地防火墙默认拒绝 + Tool Gateway 接管 | iptables / 容器网络命名空间隔离 | 未授权的外部 IP/端口调用在 OS 层必须 Fail-Closed 阻断 |
| **崩溃状态恢复** | 进程异常终止后依据本地 SQLite 账本幂等恢复 | 容器退出或 SIGKILL 后幂等恢复 | 两端均执行统一对账与恢复协议 (Reconciliation) 决水机制 |

第一阶段不引入 Kubernetes 作为强制依赖。

### 6.2 工具与凭据边界

- Agent 不因能够发现工具就自动获得调用权限。
- 所有写操作、网络访问、生产数据访问和高风险命令必须经过 Tool Gateway。
- DEV 与 QA 必须在独立身份、工作区、凭据和必要的操作系统边界上隔离。
- QA 对被测代码只读，QA 证据写入独立目录或制品存储。
- GitHub 合并凭据、生产凭据和发布凭据不得进入普通 Agent 的执行环境。
- 任务结束、超时、撤销或失败时，凭据和临时环境应能够被回收。

---

## 7. Evidence & Assurance：从证据清单升级为证据系统

### 7.1 统一 Evidence Envelope

每项证据至少应绑定：

- task_id、request_id、attempt_id；
- tested_sha、baseline_sha；
- 执行主体及其身份来源；
- Runner 身份、环境摘要和工具链版本；
- 实际执行命令、开始与结束时间、退出码；
- 原始日志和制品引用；
- Artifact SHA-256；
- 证据类型、适用 Profile 和覆盖的验收条件；
- 来源证明、采集器版本和验证状态。

### 7.2 证据评估模型、量化门槛与全生命周期异常状态机（F-07 & F-08）

**关键架构决策**：**严禁将人类授权的合并/发布（原 T5）归入 QA 证据可信等级**。
“人类批准合并”是治理生命周期的状态跃迁，而不是技术证据的更高可信度。一个项目即使被人为合并，若其缺少独立测试凭据，其证据质量依然为零；反之，一个代码通过了独立 QA 实测并持有不可篡改证据包的项目，即使尚未合并，其技术可信度依然客观成立。

#### 1. 五维证据评估模型（Evidence Quality Dimensions - F-08 第一层）

任何测试证据必须从以下五个独立维度进行质量核验，互不替代：

| 评估维度 | 核心核验问题 | 判定标准与证据要求 |
|---|---|---|
| **Provenance（来源可信度）** | 证据由谁产生、在哪里产生、是否可篡改？ | 必须附带 Runner 宿主标识、执行时间戳、物理 Commit SHA 及载荷 SHA-256 签名，杜绝匿名或本地伪造。 |
| **Reproducibility（可复现性）** | 外部独立实体能否在受控环境下复现相同测试结果？ | 必须锁定依赖版本（Lockfile）、固定输入测试向量，在隔离环境多次复跑产出确定性一致断言。 |
| **Isolation（执行隔离度）** | 执行过程是否受到被测代码或环境漂移的污染？ | 严格区分本地非隔离执行（Local）、受控只读 ACL、容器沙箱（Docker）与硬件级独立虚拟化（VM）。 |
| **Independence（主体独立性）** | 验证主体与研发主体是否在逻辑和物理上严格分离？ | DEV 与 QA 不得共享会话上下文或私钥，QA 不得对被测代码拥有写权限，必须由独立系统出具 Review。 |
| **Coverage（验收覆盖率）** | 证据是否完备覆盖了工作令声明的所有验收条件与边界？ | 证据包必须包含用例与 WORK_ORDER 验收条款的逐项映射矩阵，核心分支与禁止路径检查 100% 覆盖。 |

#### 2. 任务风险驱动的 Profile 量化门槛与治理规范（F-08 第二层）

依据任务类型与影响面，FPF 定义四类标准任务 Profile 的最低证据要求：

| Profile | 适用场景与风险等级 | 适用环境与执行隔离 | 主体独立性与签字要求 | 确定性量化门槛 |
|---|---|---|---|---|
| **Docs Profile** | 纯文档、注释、规范文本（低风险） | Local Worktree | 独立平台 QA 只读审查 | 100% Markdown 语法无错<br>100% 外部链接可达<br>100% 严格限定在 `allowed_paths` |
| **Library Profile** | 独立函数库、工具模块、纯代码（中风险） | Docker 沙箱或 Windows 只读 ACL | 独立 QA Runner / 独立模型会话 | 100% 单元测试通过 (0 Fail)<br>100% 验收断言逐条覆盖<br>100% 无禁止路径修改 |
| **Core Profile** | 核心架构、状态机、数据契约、网关（高风险） | 容器隔离或独立 OS 账户 | 独立 QA 主体 + 远端实机 Actions 物理 Artifact | 100% 全量回归测试通过 (0 Fail)<br>100% 核心分支路径覆盖<br>100% 物理哈希防篡改对齐 |
| **Release Profile** | 正式版本发布、线上环境部署（极高风险） | 强隔离 VM 或受限预发实机 | **三主体防兼任铁律**：DEV 作者、独立 QA、人类发布授权人必须为三个完全独立的账号与私钥 | 100% 全量套件与 E2E 绿灯<br>100% 覆盖跨平台兼容矩阵<br>100% 干净工作树（0 未跟踪/未提交） |

- **例外豁免治理规程与不可豁免项铁律（Exception Waiver Governance - C-07）**：
  若因不可抗力或紧急抢修需临时降级 Profile 门槛，严禁隐式绕过，必须由人类负责人签发正式的 `POLICY_WAIVER` 事件，记录风险评估、降级理由、明确有效期（默认最长 72 小时）与补偿测试承诺，在项目地图中公开归档。
  **五项绝对不可豁免项（Non-Waivable Hard Invariants）**：
  1. **人类最终合并与发布授权**：严禁由 Agent 自行签发批准合入主干（`MERGED`）或生产发布；
  2. **DEV 与 QA 主体完全独立性**：DEV 作者与 QA 审查主体账号与私钥绝对禁止兼任；
  3. **工作令授权范围与禁止路径**：严禁豁免 `allowed_paths` 与敏感治理配置文件的防越权修改门禁；
  4. **凭据隔离、只读 ACL 与审计完整性**：严禁授予 QA 被测工作树写入权，严禁向普通 Worker 注入长期高权限密钥；
  5. **外部未证明副作用严禁自动重发**：无法证明远端绝对未执行时，严禁豁免重发限制。
  **时效与逾期降级契约**：`POLICY_WAIVER` 达到 72 小时上限必须自动失效；豁免中约定的补偿测试任务必须在指定时间内完成并通过独立 QA；若补偿测试逾期未完成，系统立即强制将工单与项目状态转入 `HUMAN_RESOLUTION_REQUIRED`，冻结进一步发布。

#### 3. 完备的治理生命周期状态机与全阶段异常迁移规则（F-07 & C-05）

生命周期严格由确定性事件驱动，覆盖正常与异常分支，任何阶段不可凭自由文本跳跃：

```
                              ┌─────────────────────────────────────────────────────────────┐
                              │                      [全局授权撤销 / 漂移]                   │
                              ▼                                                             │
                       ┌──────────────┐                                                     │
                       │   REVOKED    │ <───────────────────────────────────────────────────┤
                       └──────────────┘                                                     │
                              ▲                                                             │
DRAFT_WORK_ORDER ──> DISPATCHED ──> DEV_SUBMITTED ──> INDEPENDENT_QA_EVALUATING ────────────┤
       │                                                      │                             │
       │                                                      ├─[环境故障/脚本错误]─> INVALID_TEST (重试预算<=2)
       │                                                      │                         │ (超出预算)
       │                                                      ├─[依赖冲突/远端分歧]─> BLOCKED ───┤
       │                                                      │                         │ (对账决水成功)
       │                                                      │                         ▼
       │                                                      │                    DISPATCHED
       │                              ┌───────────────────────┴───────────────────────┐
       │                              ▼                                               ▼
       │                        QA_VERIFIED (PASS)                              QA_FAILED
       │                              │                                               │ (绑定失败制品与计数)
       │                      ┌───────┴───────┐                                       ▼
       │                      ▼               ▼                               DEV_REWORK_LOOP
       │               HUMAN_APPROVED   HUMAN_REJECTED (人类否决)                     │ (超过最大返工次数)
       │                      │               │                                       │
       │                      ▼               ▼                                       ▼
       │                    MERGED        ARCHIVED ──────────────────────> HUMAN_RESOLUTION_REQUIRED
       │                      │                                                       ▲
       │                      ▼ (线上故障回滚)                                        │ (回滚执行失败)
       │              ROLLBACK_WORK_ORDER ──> ROLLBACK_EXECUTING ──> ROLLBACK_QA_EVALUATING
       │                                                              │ (QA PASS)
       │                                                              ▼
       │                                                    ROLLBACK_QA_VERIFIED
       │                                                              │ (人类授权)
       │                                                              ▼
       │                                                   ROLLBACK_HUMAN_APPROVED
       │                                                              │ (主干合入)
       │                                                              ▼
       │                                                         ROLLED_BACK
```

**全阶段异常分支契约**：
1. **`HUMAN_RESOLUTION_REQUIRED` 正式治理状态**：
   - 进入条件：DEV 返工 attempt 超过上限（默认 3 次）、`INVALID_TEST` 超过环境重试预算（2 次）、`BLOCKED` 对账探针超时（60s）仍无法决水、或检测到非法 SHA 漂移等不可逆 `REMOTE_CONFLICT`；
   - 状态行为：完全冻结一切自动调度与外部重试，持久化分歧证据包；
   - 退出条件：人类负责人持有专属私钥签发人工裁定事件：
     - `HUMAN_RESOLVED`：指定决水版本与修复策略，重置 attempt 计数并恢复至 `DISPATCHED`；
     - `HUMAN_ABORT`：终止任务并直接转入 `ARCHIVED`。
2. **`REVOKED` 全局覆盖与阻断契约**：
   - 适用范围：覆盖除终态之外的所有活动状态（`DISPATCHED`、`DEV_SUBMITTED`、`INDEPENDENT_QA_EVALUATING`、`QA_VERIFIED` 人类批准前、`HUMAN_APPROVED` 主干合入前）；
   - 触发原因：人类主动撤销、工作令非法篡改、上游主干基线发生漂移；
   - 触发动作：系统同步回收临时凭据、杀死进程树、清理工作区，未完成制品永久作废；已合入（`MERGED`）或发布（`RELEASED`）的任务严禁倒退到 `REVOKED`，必须走 `ROLLBACK` 治理通道。
3. **`HUMAN_REJECTED` 路径与语义纠偏**：
   - 人类负责人在 `QA_VERIFIED` 后进行独立审批，形成二选一决策分支：批准合入（`HUMAN_APPROVED` -> `MERGED`）或否决归档（`HUMAN_REJECTED` -> 附注否决原因直接进入 `ARCHIVED`）；杜绝 `HUMAN_APPROVED` -> `HUMAN_REJECTED` 的非法跃迁。
4. **`INVALID_TEST` 独立环境重试预算（Environment Retry Budget）**：
   - 针对测试环境故障、依赖拉取超时、Runner 崩溃等非代码缺陷中断，状态置为 `INVALID_TEST`；设立独立重试计数（默认上限 2 次），**绝对不计入 DEV 业务代码返工次数**；重试耗尽强制转入 `HUMAN_RESOLUTION_REQUIRED`。
5. **`BLOCKED` 状态精确解除条件**：
   - 仅在导致阻塞的根本原因（如前置工单合并、远端 SHA 冲突决水完成）经权威事实核验消除，并由 Reducer 生成 `UNBLOCKED` 事件后，方可恢复至 `DISPATCHED`；不得因偶发单次网络请求成功就假定解除。
6. **远端取消与完成的异步竞态对账契约（Cancellation & Completion Race - C-05）**：
   - 远端取消绝非瞬间完成，本地发出取消指令后，严禁直接将远端任务假定为已取消；
   - 本地状态细化为：
     - `CANCEL_REQUESTED`：本地已发出取消意图；
     - `CANCEL_PENDING`：等待远端权威系统确认回执；
     - `REMOTE_CANCELLED`：远端确认取消成功，回收资源并安全归档；
     - `REMOTE_SUCCEEDED`：远端在取消到达前已执行成功；
     - `CANCEL_CONFLICT`：取消与完成发生并发竞争，对账引擎必须重新对账并核验产物哈希，严禁丢弃已生成的有效制品。
7. **ROLLBACK 完整治理生命周期契约（Full Rollback Lifecycle - C-05）**：
   - 触发条件：已合入（`MERGED`）或发布（`RELEASED`）的代码发生重大线上故障，必须由人类负责人签发正式的 `ROLLBACK_WORK_ORDER`；
   - 规范统一状态流转体系：
     `ROLLBACK_WORK_ORDER`（人类签发回滚令，状态为 `DISPATCHED`）
     ──> `ROLLBACK_EXECUTING`（生成明确的反向 Git Commit SHA）
     ──> `ROLLBACK_QA_EVALUATING`（独立 QA Runner 执行回归测试）
     ──> `ROLLBACK_QA_VERIFIED`（独立 QA 验证通过，产出物理回滚证据包）
     ──> `ROLLBACK_HUMAN_APPROVED`（人类负责人签署回滚合入授权）
     ──> `ROLLED_BACK`（反向 Commit 合入主干，状态终态归档）；
   - 异常接管：若回滚执行发生合并冲突或 QA 测试未通过，系统绝对禁止反复自动重试，必须立即跃迁至 `HUMAN_RESOLUTION_REQUIRED`，冻结变更并转入人工紧急接管。

#### 4. 向后兼容的执行记录标签（Historical Capture Tags）

为兼容旧版执行日志，保留以下四个纯技术记录标签（仅代表执行手段，不代表治理状态）：
- **T0（Agent 自述）**：无结构化证据的会话回复，系统可信度视同为零。
- **T1（本地观察与日志）**：本地进程输出日志，证明在本地环境发生过调用，不保证环境隔离与独立性。
- **T2（确定性测试套件）**：固定本地环境中的自动化测试输出，证明代码符合既定断言。
- **T3（隔离 Runner 与不可篡改 Artifact）**：在隔离 Runner 中执行产生、带有物理 SHA-256 哈希的制品包。
- *注：原 T4（独立 QA）升级为独立的 `QA_VERIFIED` 治理状态与五维量化审计；原 T5 升级为人类专属的 `HUMAN_APPROVED` 与 `MERGED` 治理行为。*

### 7.3 风险驱动的 QA Profile

沿用 Library、API-DB、Full-Stack、Rework 等现有 Profile，逐步建立风险映射：

- 文档类：路径、格式、链接、内容和编码检查。
- 普通业务代码：单元测试、回归、Diff、SHA 和覆盖范围。
- API / 数据库：真实接口、事务、持久化、迁移和异常恢复。
- 全栈功能：真实浏览器、E2E、DOM、控制台和关键用户路径。
- 安全与治理代码：权限对抗、路径逃逸、身份分离、策略回归和独立审核。
- 返工任务：原失败用例必须能够复现旧缺陷，并验证修复后的行为。

Profile 由任务风险、技术范围和验收条件决定。不得通过选择较弱 Profile 或声明 NOT_APPLICABLE 来规避必要验证。

### 7.4 证据语义校验

文件存在和哈希一致只是基础，不代表证据语义成立：

- 测试命令必须真正覆盖对应验收条件。
- 空命令、无意义 echo、预置截图不能证明功能通过。
- API 证据必须绑定真实请求和响应。
- 数据库证据必须绑定真实连接、事务和持久化检查。
- 浏览器证据必须绑定真实页面执行、DOM 断言和必要截图。
- QA Plan 必须来自受保护、独立审核的版本。
- Artifact 必须绑定工作流、Runner、固定 SHA 和独立审查主体。

---

## 8. 分阶段迭代路线图

路线图采用“先标准、后内核；先单机可靠、后多机扩展；先证明、后自治”的顺序。

### 8.0 上游宏观阶段与细分研发阶段映射矩阵

为保持与上游架构战略四阶段管理的显式对齐，同时兼顾研发实施的高内聚切片颗粒度，FPF 2.0 的分阶段路线建立如下映射对照体系：

| 上游宏观阶段 | 正文细分阶段 | 核心建设目标 | 交付形态 |
|---|---|---|---|
| **第一阶段：标准化与核心内核** | **阶段 0**（架构清账与规范边界）<br>+ **阶段 1**（Core Kernel 与确定性状态机） | 规范化五权契约、定义 Schema、实现无副作用纯函数 Reducer | 规范文档、JSON Schemas、核心 Kernel 包 |
| **第二阶段：可靠执行** | **阶段 2**（Control Plane 与可靠协调）<br>+ **阶段 3**（Portable Execution Runtime） | 落地 Reconciliation Protocol、支持 Windows 11 原生与 Docker 双后端 | 统一调度器、Thread Bridge、三层 Runner、Tool Gateway |
| **第三阶段：可信验证** | **阶段 4**（Evidence Engine & Conformance Kit） | 建立五维证据系统，独立交付 Conformance Suite 与 Agent Eval | 证据采集与验证器、符合性测试套件 CLI、模型评测框架 |
| **第四阶段：标准化发行** | **阶段 5**（Bootstrap、发行与生态兼容） | 具备第三方项目独立初始化、Doctor 诊断、升级迁移与稳定交付 | FPF CLI (init/doctor/status/conformance)、参考模版、发行包 |
| **持续工程扩展（可选）** | **阶段 6**（Continuous Engineering 扩展） | 生产反馈回流、只读故障诊断；作为 **2.1+ 可选路线**，明确不阻塞 2.0 稳定版 | 生产指标适配器、只读排障 Agent、热修复工单触发器 |

---

### 阶段 0：架构标准化与现状清账

**优先级：P0｜先完成**

目标：冻结 2.0 的架构边界，避免后续每增加一个功能就改变一次底层结构。

交付物：

1. FPF 2.0 架构与模块职责规范。
2. 当前能力清单：MAIN、DRAFT、EXPERIMENTAL、NOT_RUN、PLANNED。
3. 核心对象和事件模型草案。
4. 五权不变项与可配置实现项清单。
5. RFC、Schema、Runtime、Dispatch、Evidence 的版本关系和兼容策略。
6. 当前文档中“GitHub 唯一事实源”与“本地 Runtime Ledger”等表述的边界说明。

验收条件：

- 每一项能力都有明确的代码位置、状态和证据来源。
- 不存在把 Draft PR、接口定义或模拟测试描述为已上线能力的情况。
- 模块之间不存在重复定义状态、身份和证据语义的情况。
- 架构文档能够指导独立开发者实现适配器，而不依赖当前项目对话上下文。

### 阶段 1：Protocol & Core Kernel

**优先级：P0｜2.0-alpha 的基础**

**本阶段并入复盘项：** H4（范围修正协议 `SCOPE_AMEND`，`PLAN_ONLY`）。协议与 Schema 在阶段 1 定义，强制拦截依赖 G2/G4。

目标：建立与外部模型和平台无关的确定性核心。

交付物：

1. 统一 Project Manifest、Principal、Capability Profile、Work Order、Scope Grant、Task Event 等 Schema。
2. 统一事件信封、版本字段、幂等键和关联 ID。
3. 将核心状态机整理为纯函数 Reducer。
4. 建立 Policy Engine 的统一输入输出和拒绝原因。
5. 定义 Governance Backend 接口，GitHub Adapter 作为第一参考实现。
6. 明确 Runtime Ledger 与 Dispatch Journal 的职责和事件互操作契约。

验收条件：

- 同一组已验证事件在不同运行环境下得到相同状态结果。
- 重复事件、乱序事件、过期授权、撤销授权和 SHA 漂移均有确定性测试。
- Reducer 不直接调用 GitHub、模型、文件系统或外部网络。
- 更换治理后端不需要修改状态机核心。
- 运行账本不能覆盖或伪造远端权威事实。

### 阶段 2：Control Plane 与可靠协调（落地对账恢复与 Transactional Outbox）

**优先级：P0/P1｜2.0-alpha**

**本阶段并入复盘项：** G2（宪制强制力，前置）、G3（凭据与身份边界）、G4（状态机归约接入）、H1（项目注册的控制面部分）；均为 `PLAN_ONLY`。

目标：让任务可以安全派发、观测、恢复和有界重试，落地 Transactional Outbox 与 Provider 幂等分级对账协议。

交付物：

1. 统一 Dispatcher、Scheduler、Reconciler 和任务队列接口。
2. 落地正式的**对账与恢复协议（Reconciliation Protocol）**，支持 Provider Class A/B/C 三级幂等分级与 60 秒探针退避决水机制。
3. 落地 **Transactional Outbox 模式**，在同一个原子事务中完成 CAS 版本比对、事件落盘与发件箱写入。
4. 统一 Request ID、Attempt ID、Idempotency Key、Causation ID、Receipt 和 Observation。
5. 实现外部未知副作用（`UNKNOWN_OUTCOME`）恢复算法，执行 `NOT_FOUND ≠ PROVEN_NOT_EXECUTED` 延迟窗口校验。
6. 统一 Runtime 与 Dispatch 的生命周期事件流，执行 `PROJECTION_ONLY` 回放零副作用硬防护。
7. 建立并发锁、超时、取消、退避、熔断和人工接管机制。
8. 接入 GitHub 参考后端，形成权威字段映射（严格校验 Review Commit SHA）与可复核的任务流。

验收条件：

- 进程在派发前后、回执前后和轮询过程中中断，恢复后**严禁盲目重复发送**，必须通过探针决水。
- 数据库提交后进程崩溃不丢事件，通过 Outbox 保证 At-Least-Once 投递与下游幂等消费。
- 状态推进必须重新读取并验证规范事实；本地账本与远端冲突时触发 `REMOTE_CONFLICT` 阻断。
- QA FAIL 深度绑定失败日志与 SHA，受最大重试次数约束；QA PASS 只能到达人工合并门禁。
- 未确认的取消、未知回执和外部服务异常必须阻断并要求执行 Reconciliation Protocol。
- 至少完成一次真实 DEV → 独立 QA → FAIL → DEV 返工 → PASS → 人工合并门禁的端到端演练。

### 阶段 3：Portable Execution Runtime（三层后端与跨平台支持）

**优先级：P1｜2.0-beta**

**本阶段并入复盘项：** H2（worktree 生命周期，`PLAN_ONLY`）。

目标：让 Agent、模型和执行环境可以替换，保持 Windows 11 原生生产级一级支持与 Docker 隔离执行。

交付物：

1. AgentProvider 统一接口与模型适配器。
2. ExecutionBackend 统一抽象与三层后端（Local Worktree、Docker Sandbox、Ephemeral VM 契约）。
3. Local Worktree（Windows 11 原生一级支持）与 Docker Sandbox（Linux 容器隔离）两个首批生产级 Runner。
4. Tool Gateway 和 Capability Profile，接管文件写操作、网络出站与高风险命令。
5. Credential Broker 与临时凭据隔离管理，支持 Windows DPAPI 与 Linux 临时挂载。
6. 任务级时间、Token、并发和费用预算控制器。
7. Agent Session 的创建、恢复、取消和结果回传。
8. Windows 11（PowerShell 7+、NTFS、Job Objects）与 Ubuntu（Bash、ext4、cgroups）跨平台支持矩阵与实机验证记录。

验收条件：

- 同一工作令可以通过至少两种 Agent/模型适配器执行，核心治理代码无需修改。
- 同一 Agent 可以平滑切换 Windows 11 Local Worktree 与 Docker Runner，核心任务契约与路径规范完全不变。
- Windows 11 原生环境下的路径反斜杠、大小写与进程树生命周期经过实测，无僵尸进程残留。
- DEV 和 QA 的文件系统、凭据和写权限实现有效隔离（QA 对被测源码严格只读）。
- 不允许 Agent 通过 Shell、浏览器或其他工具绕过 Capability Policy。
- 任务结束后能够彻底清理临时环境和凭据。
- 超时、资源耗尽和外部 Provider 不可用时均有明确状态和恢复策略。

### 阶段 4：Evidence Engine & Conformance Kit（确定性契约测试与模型评测严格分轨）

**优先级：P1｜2.0-rc**

**本阶段并入复盘项：** H3（部署就绪门禁，`PLAN_ONLY`）；H1 的 Conformance 校验部分。

目标：把“能执行”升级为“可证明、可复核、可移植”，严格剥离确定性系统契约测试与概率性模型评测。

交付物：

1. 统一 Evidence Envelope（绑定五维模型最低要求）、Manifest 与 Attestation 签名工具。
2. Evidence Collector、Evidence Store 与具备 Profile 门禁的 Evidence Verifier。
3. 独立治理生命周期状态机校验器（支持 BLOCKED、QA_FAILED、REVOKED 等全状态转换）。
4. 独立 QA Runner 与平台认证 Artifact 物理哈希绑定。
5. **产品 A：FPF Conformance Suite（系统协议确定性硬门禁套件）**：
   - **Protocol 契约**：事件格式、因果 sequence、原子 CAS 版本并发控制与 `PROJECTION_ONLY` 回放零副作用校验。
   - **GovernanceBackend 契约**：Issue/PR/Review/Commit 字段映射与非事务冲突判定。
   - **AgentProvider 适配器契约测试**：**使用固定的 Mock Provider** 测试适配器报文编码、身份注入、`idempotency_key` 传递、超时中断与异常映射，**不评测真实模型生成质量**。
   - **Runner 契约**：Local Worktree（只读 ACL 与 Job Objects 进程回收）与 Docker Sandbox 资源隔离边界测试。
   - **ToolGateway 契约**：权限对抗测试、越权拦截与敏感凭据脱敏测试。
6. **产品 B：FPF Agent Evaluation（大模型可靠度统计评测框架）**：
   - 独立测试真实大模型在 Agent 提示词与上下文环境下的行为稳定性（如面对模糊工作令主动澄清、对抗性越权诱导拒绝、多步返工代码对齐、超长上下文抗漂移）。
   - 绑定特定模型版本（如 GPT-5、Claude 3.5 Sonnet、DeepSeek）、Prompt 模板版本与评测数据集，出具含成功率、方差与置信区间的统计学评测报告。
7. 独立发行的 `fpf conformance` CLI 工具包，供第三方项目自测规范兼容性。

验收条件：

- 所有正式 QA 结论均绑定固定 SHA、独立主体、五维合规评估与可验证 Artifact。
- 证据被篡改、来源缺失、测试命令无效或覆盖不足时，验证器必须拒绝 PASS。
- **Conformance 100% 判定基准基于“声明能力集模型（Declared Capabilities）”**：
  - 判定公式：`Declared Capabilities` -> `Applicable Test Set` -> `Mandatory Security Tests (通用安全硬门禁)` -> `PASS`；
  - 适配器必须通过其所声明能力对应的所有适用性契约测试，且**必须 100% 通过通用安全测试**（越权阻断、SHA 漂移拦截等）；禁止通过未声明核心功能来逃避安全检查。
- **Conformance Suite 与 Agent Evaluation 形成独立版本和独立产物，互不替代**：
  - 只有通过 Conformance Suite，系统方可声称“符合 FPF 2.0 规范”；
  - Agent Evaluation 仅作为模型在 FPF 环境下的可靠度评分参考，不作为系统符合性阻断项。
- 新 Agent 在无历史对话的情况下，能够通过标准基准任务并正确拒绝越权。
- FPF 自身每次修改规范、Schema、Hooks 和治理核心时，自动触发 Conformance 回归。

### 阶段 5：Bootstrap、发行与生态兼容

**优先级：P1/P2｜2.0.0 稳定版**

**本阶段并入复盘项：** H1（`projects/<id>/project.yaml` 注册表与发行校验，`PLAN_ONLY`）。

目标：使 FPF 能够被第三方项目独立安装、配置、升级和验证。

交付物：

1. 标准 Project Manifest 和项目配置 Profile。
2. Bootstrap 对规范版本、后端、适配器和 Runner 的兼容检查。
3. CLI：init、doctor、conformance、status、run、reconcile 等稳定命令。
4. 一键生成项目治理基线、工位、策略和测试配置。
5. Schema / Package / Adapter 版本兼容矩阵。
6. 迁移、升级、回滚和故障诊断机制。
7. 最小示例项目和第三方接入指南。
8. 稳定发行包、版本说明和安全策略。

验收条件：

- 在一个干净的外部测试仓库中，不依赖 FPF 自身的历史上下文即可完成初始化。
- 初始化后能够通过 Doctor 和 Conformance 检查。
- 更换模型、Runner 或治理后端时，项目治理规则和验收契约保持一致。
- 新版本升级不会静默改变权限、状态或证据语义。
- 第三方开发者可以仅依据规范和 Conformance Kit 实现一个兼容适配器。

### 阶段 6：Continuous Engineering 扩展

**优先级：P2｜建议作为 2.1+ 可选扩展，不阻塞 2.0**

目标：将 FPF 从软件交付闭环延伸到软件运行维护闭环。

可选能力：

- 生产日志、指标、Trace 和用户反馈接入。
- Agent 只读诊断与故障归因。
- 自动形成问题 Issue、复现步骤和修复工作令。
- 进入标准 FPF DEV / QA / Rework 流程。
- 发布前后指标对照、Canary 和回滚验证。
- 运行知识与历史故障经验回流项目 Context。

安全边界：

- 生产数据默认只读，并进行脱敏。
- Agent 可以诊断、提出修复和准备发布方案。
- 合并、发布和生产写操作仍须经过明确的人类授权或另行批准的受限策略。
- 生产自动化不能成为绕过五权分立的旁路。

### 8.7 复盘新增项：G2–H4（2026-11-11 并入）

本节把 2026-11-10 复盘出的 7 项挂入既有阶段，不新开第三份文档。**截至 2026-11-11，7 项全部为 `PLAN_ONLY`：没有任何一项已经实现、生效或通过实机验证。**

#### 8.7.1 依赖顺序与并行边界

强制力生效顺序（不是文档写作顺序）：

```text
G2 宪制强制力 → G3 凭据与身份边界 → G4 状态机归约 → H1 项目注册
→ H2 worktree 生命周期 → H3 部署就绪门禁 → H4 范围修正协议
```

- **为什么 G2 排第一：** 没有平台级或密码学级强制力时，G3–H4 的拦截都只是建议。`validate-card` 再严格，也建立在“仓库内策略代码不被改弱、workflow 不被停用、审批人不兼任”的前提上，而这些前提当前没有第二道门。
- **可并行起草：** H1 的 manifest 字段、H2 的 `.fpf-worktree.json` 格式、H4 的 `SCOPE_AMEND` Schema 可在阶段 1–2 并行设计；H3 的容器 smoke 脚本可先在 geo-service-core 试点，但“事件触发 + 强制断言”必须等 G4 提供事件源。
- **不可并行生效：** G4 的 reducer 必须消费 G3 定义的 Principal/凭据事件；H2 的自动回收必须由 G4 的 merge 事件驱动；H3 的部署门禁必须由 G4 的 release 事件驱动。

#### 8.7.2 G2 · 宪制强制力落地

- **落点阶段：** 阶段 2（Control Plane）前置门禁；状态 `PLAN_ONLY`。
- **问题定义：** 当前强制力由“仓库内 check + 人工纪律”叠加而成。GitHub 原生 `required_approving_review_count=0`，CODEOWNERS 指向负责人本人；修改策略代码的 PR 虽然要求第二名独立批准，但 `sovereign_override` 允许作者本人放行；DEV 与 QA 的“独立身份”只体现为登录名不同，密钥仍在同一台宿主机。
- **反例证据：** 2026-11-11 实测 `GET /repos/huangzuomin/five-powers-flow/branches/main/protection`：`enforce_admins=true`，但 `required_approving_review_count=0`；`.github/CODEOWNERS` 全部指向 `@huangzuomin`；`packages/fpf_policy/pr_gate.py` 的 `GATE_PR` 分支在缺少第二批准时，只要 `sovereign_override=true` 且 `sovereign_authorizer == author` 即放行。复盘记载的 `403 Upgrade to GitHub Pro` 发生在私有仓库阶段，当前仓库已 PUBLIC，该报错不再复现——这恰好证明强制力会随仓库可见性与套餐漂移，不能作为宪制基础。
- **目标行为：** 二选一或叠加：①启用 GitHub Rulesets + required approvals + 独立 QA team，让平台层拒绝“自审自批”；②不依赖套餐，改用“制品签名 + 独立校验器”——QA 产物由独立私钥签名，合并门禁验证签名链与 SHA 绑定，而不是只比对登录名。
- **验收标准（可测）：**
  1. 无独立 QA 批准的 PR 在平台层无法合并（API 返回 405/422 或 required check 失败），并留存一次真实拒绝记录；
  2. `required_approving_review_count >= 1` 且批准人 ≠ PR 作者 ≠ 策略修改人；或签名校验器对未签名/错签制品返回非零退出码；
  3. 修改 `packages/fpf_policy/`、`.github/` 的 PR 需要两名不同身份批准，测试覆盖“同一人二次批准被拒”。
- **依赖：** G3 定义 Principal 与密钥归属；H1 定义项目边界。
- **与既有阶段边界：** 阶段 2 已有人工审批节点，G2 只补“平台/密码学强制”，不重写 24 状态机。

#### 8.7.3 G3 · 凭据与身份边界

- **落点阶段：** 阶段 2；状态 `PLAN_ONLY`。
- **问题定义：** 仓库可以做到零跟踪密钥，但开发机上仍可能存在未加密、未忽略、权限过宽的私钥；bot token、签发私钥与 DEV 环境共享同一文件系统，所谓“独立 QA 身份”没有物理边界。
- **反例证据：** 本机 `D:\SSOT\Work\FPF自动化开发工作流\.inflow-setup\issuer_private_key.hex`，64 字节 Ed25519 种子，未加密、未跟踪；2026-11-11 开工时受版本控制的 `.gitignore` 未覆盖 `.inflow-setup/`。同目录还有 `collector_token.txt`（55 字节）。本 PR 的 Phase 0 提交已补 `.gitignore`（`.inflow-setup/`、`secrets/`、`*.hex`），但**密钥未轮换，按已暴露处理**。
- **目标行为：** 仓库零密钥；merge/governance/QA bot token 只进 CI secrets 或 OS 凭据库；pre-commit 与 CI 双密钥扫描；签发私钥不落盘到工作区；轮换与吊销有可核验记录。
- **验收标准（可测）：**
  1. `git ls-files` 与 `git grep` 对私钥模式零命中；
  2. pre-commit 对“故意植入的测试私钥”返回非零并阻断提交（有自动化用例）；
  3. CI secret scanning 在 PR 上启用，命中即 fail-closed；
  4. 受影响私钥完成轮换，旧公钥指纹进入吊销列表，轮换事件有 SHA/时间/操作者记录；
  5. QA bot 私钥只存在于 OS 凭据库或 CI secret，`Get-ChildItem` 在工作区零命中。
- **依赖：** G2（身份与审批模型）。
- **与既有阶段边界：** 不替代阶段 3 的 Credential Broker 设计；G3 先解决“静态密钥不落盘”，Broker 解决“运行时短时令牌”。

#### 8.7.4 G4 · 状态机归约接入

- **落点阶段：** 阶段 2（与 §4.1 对账恢复协议对接）；状态 `PLAN_ONLY`。
- **问题定义：** 24 状态机已作为库存在（`packages/fpf_coordinator/dispatch/`，含 CAS journal 与测试），但没有消费 GitHub 事件；任务状态由人/Agent 手写卡片和地图维护，人的记忆与仓库事实之间没有自动对账。
- **反例证据：** `docs/coordination/project-map.md` 的 `DONE / PASS / MERGED / DEPLOYED` 全部是手写表格；PR #67 的 `Draft/BEHIND` 是本次开工靠 `gh pr view` 人工巡检才发现，不是系统告警；`dispatch` 包没有任何 webhook/event 消费者。
- **目标行为：** GitHub Issue/PR/Review/CheckRun/WorkflowRun 事件 → 规范化 `Task Event` → 纯函数 reducer → 只读投影；人不再手写状态；投影与远端事实不一致时自动 `BLOCKED` 并生成对账包。
- **验收标准（可测）：**
  1. 同一组事件重放两次得到逐字节相同的投影；
  2. 重复事件、乱序事件、过期授权、SHA 漂移均有确定性测试；
  3. 至少一个真实 PR 从 `DRAFT_WORK_ORDER` 到 `MERGED` 全程由事件驱动，零人工状态编辑；
  4. 人为篡改投影后，对账任务能在一次轮询内发现并 `BLOCKED`；
  5. reducer 不直接调用 GitHub、模型、文件系统或网络（静态检查）。
- **依赖：** G3（Principal/凭据事件）、§4.1 的两层状态机与探针协议。
- **与既有阶段边界：** G4 不新增第二套状态机；它把现有 24 状态机接到事件源，并复用 §4.1 的 `Reconciliation Protocol` 处理未知结果。

#### 8.7.5 H1 · 项目注册与控制面隔离

- **落点阶段：** 阶段 2（控制面隔离）与阶段 5（发行校验）；状态 `PLAN_ONLY`。
- **问题定义：** FPF 没有项目注册表，无法从仓库事实回答“这个项目是否受 FPF 管理、用哪个后端、跑哪个 Profile、允许改哪些路径”。控制面仓库也没有机制阻止业务代码混入。
- **反例证据：** 2026-11-11 在 main 上 `Test-Path .fpf/project.yaml` 为 `False`；仓库不存在 `projects/<id>/` 目录；`docs/BOOTSTRAP.md` 描述的初始化产物未以 manifest 形式提交，Bootstrap 结果无法被后续门禁复用。
- **目标行为：** 每个受管项目有 `projects/<id>/project.yaml`（项目 ID、仓库、治理后端、默认 Profile、allowed_paths、负责人、预算/TTL）；控制面仓库零业务代码，由 CI 路径白名单校验；`fpf project validate` 可离线校验。
- **验收标准（可测）：**
  1. 新项目初始化后生成 `projects/<id>/project.yaml`，`fpf project validate` 退出码 0；
  2. 控制面仓库出现业务代码路径时 CI 失败（有反例用例）；
  3. manifest 与 PR 的 `task_id`、`allowed_paths`、Profile 不一致时 `validate-card` 阻断；
  4. 至少一个外部项目以 manifest 接入并通过 Conformance（阶段 5）。
- **依赖：** 阶段 1 的 Project Manifest Schema；G2 的项目级审批。
- **与既有阶段边界：** 不替代 Bootstrap；H1 只定义“注册与隔离事实”，Bootstrap 负责“生成与迁移”。

#### 8.7.6 H2 · worktree 生命周期

- **落点阶段：** 阶段 3（Portable Execution Runtime）；状态 `PLAN_ONLY`。
- **问题定义：** worktree 创建后没有标记、没有 TTL、没有回收触发条件，合并/放弃的任务长期占用磁盘与分支命名空间，dirty worktree 还可能被误当成有效工位。
- **反例证据：** 2026-11-10 复盘实测跨仓库 196 个 worktree、19 个 dirty、约 20–38 GB；2026-11-11 本机 `git worktree list` 仍有 18 条记录（含主工作区），`_worktrees/` 占 0.4 GB，且无任何自动回收记录。
- **目标行为：** 每个 worktree 带 `.fpf-worktree.json`（task_id、base_sha、branch、owner、created_at、ttl、state）；merge 事件把 state 置为 `RECLAIMABLE`；回收必须同时满足“工作树干净、无未推送提交、分支已合并”三条件并受 TTL 约束；默认 dry-run，删除留审计。
- **验收标准（可测）：**
  1. 创建 worktree 自动写入标记，字段缺一即失败；
  2. merge 事件后标记变为 `RECLAIMABLE`；
  3. 三条件任一不满足时回收被拒绝（3 个独立测试）；
  4. TTL 到期只告警，不自动删除 dirty/未合并 worktree；
  5. 每次回收产出审计记录（路径、branch、SHA、原因、操作者）与回收前后磁盘报告。
- **依赖：** G4 的 merge 事件；阶段 3 的 Runner 生命周期接口。
- **与既有阶段边界：** 不删除任何现有 worktree；H2 只定义未来的标记、判定与回收协议。

#### 8.7.7 H3 · 部署就绪门禁

- **落点阶段：** 阶段 4（Evidence Engine）；状态 `PLAN_ONLY`。
- **问题定义：** “迁移脚本打印 PASS”不等于“目标库已到 head”。部署前没有容器 smoke、没有 `alembic_version == head` 断言，迁移失败会被上层的成功输出掩盖。
- **反例证据：** 复盘记录：部署流程打印 `migrate PASS`，但 `.53` 实库 `alembic_version` 仍为 `0036`；geo-service-core PR #358 的背景核查显示 8001 未监听、`inflow_*` 六表不存在，最终以新增 `0037_inflow_data_plane_tables` 迁移补救（PR #358 合并于 2026-11-11T03:07:39Z，merge commit `fd7bc736999cd8ad75b2bdd8cd8de6c80bba9106`）。
- **目标行为：** diff 命中 `infra/`、`backend/migrations/` 或部署编排文件时，强制在目标预发环境执行：①容器启动 smoke（健康端点/端口监听）；②`alembic_version == head` 断言；③关键表存在性断言。证据绑定被测 SHA、镜像摘要与数据库版本。
- **验收标准（可测）：**
  1. 门禁在真实预发库上运行，输出含 `tested_sha`、`image_digest`、`alembic_version`、`head`；
  2. 注入“版本落后一档”的测试库时门禁返回非零并阻断；
  3. 只改文档/不影响 infra 的 PR 不触发该门禁（避免形式主义）；
  4. 部署授权仍由人类签署，门禁只证明“就绪”，不代替部署批准。
- **依赖：** G4 的 release/deploy 事件；阶段 4 的 Evidence Envelope 与 Artifact 校验。
- **与既有阶段边界：** 不新增部署自动化；H3 是“部署前必须存在的证据断言”，生产部署与真实计费仍 `NOT_AUTHORIZED`。

#### 8.7.8 H4 · 范围修正协议

- **落点阶段：** 阶段 1（Protocol & Core Kernel）；状态 `PLAN_ONLY`。
- **问题定义：** 交付过程中扩大范围时，没有事前授权卡片；范围扩张只能在新 PR 描述里事后解释，`allowed_paths` 与 `SCOPE_GRANT` 失去约束力。
- **反例证据：** geo-service-core PR #358 在“INF-COLLECTOR-01 部署启用”中新增 `0037_inflow_data_plane_tables` 迁移；其前序交付 PR #357 的范围不含该 schema 变更，范围扩张仅由 PR #358 的正文事后说明，没有事前 `SCOPE_AMEND`。
- **目标行为：** 新增 `SCOPE_AMEND` 卡片：原工作令 ID/SHA、新增范围、理由、风险评估、请求人、人类批准人、生效基线 SHA、有效期；必须在越界 diff 进入 review 之前存在并被门禁校验；拒绝“先改后补”。
- **验收标准（可测）：**
  1. diff 超出 `allowed_paths` 且无有效 `SCOPE_AMEND` 时，`validate-card` 返回非零；
  2. `SCOPE_AMEND` 必须绑定 base SHA、批准人与工作令版本，字段缺失即拒绝；
  3. 卡片内容寻址（payload_digest），修改后旧批准自动失效；
  4. 用 0037 类场景做回归用例：先有 amend 才允许迁移文件进入 diff。
- **依赖：** 阶段 1 的 Scope Grant 契约；G2/G4 提供强制拦截与事件记录。
- **与既有阶段边界：** 不放宽 `allowed_paths`；H4 只提供“合法的范围变更通道”，不提供静默豁免。

---

## 9. 五类资产、三大产品双向验证体系与六维版本兼容矩阵（F-09）

为明确 FPF 的商业与开源发行形态，FPF 将五类工程资产归入三大独立演进的正式产品线，并建立双向验证闭环：

```
                              ┌──────────────────────────────────────────────┐
                              │ 1. FPF Standard（五权治理标准库）              │
                              │    - 规范文档 (RFC)、JSON Schemas、核心事件契约│
                              │    - 包含形式化元模式（Specification Meta-Model│
                              │    - 中立定义产品边界、权限模型与数据契约      │
                              └──────┬───────────────────────────────▲───────┘
                                     │                               │
                        规范遵循约束 │                               │ 独立验证规范元模式自洽性
                                     ▼                               │
┌──────────────────────────────────────────────┐                     │
│ 2. FPF Reference Runtime（参考执行运行时）   │                     │
│    - Core Kernel、Control Plane、三层 Runner │                     │
│    - 官方参考实现（Python/CLI），提供调度执行│                     │
└──────────────────────┬───────────────────────┘                     │
                       │                                             │
          实现合规校验 │                                             │
                       ▼                                             │
┌────────────────────────────────────────────────────────────────────┴───────┐
│ 3. FPF Conformance（符合性验证套件）                                         │
│    - 零依赖基础规范校验器（Minimal Base Spec Validator，信任根）            │
│    - 权威官方测试向量（Authoritative Golden Test Vectors）                  │
│    - Conformance CLI（GPG 签名发布，绑定 Standard 哈希锁定）                │
│    - 双向独立验证：既验证 Standard 规范自洽性，又验证 Runtime 实现合规性   │
│                                                                            │
│    [附属评测包] FPF Agent Evaluation Framework                              │
│    - 独立评测大模型在 Agent 提示词下的行为稳定性与可靠度统计指标           │
└────────────────────────────────────────────────────────────────────────────┘
```

#### 消除循环信任：Conformance 独立信任根架构与交叉验证（Root of Trust - C-06）

为彻底解决“Conformance 验证 Standard、谁来验证 Conformance”的循环信任问题，系统确立严密的独立信任根架构与交叉验证契约：
1. **规范独立元模型（Specification Meta-Model）**：Standard 内部包含形式化元模式（Meta-Schema），中立定义所有规范对象的不变性公理与合法语法。
2. **零依赖基础校验器与独立双实现交叉验证（Dual-Implementation Cross-Verification）**：
   - Minimal Base Spec Validator 必须存在至少两个完全独立的纯函数实现（如 Python 纯函数实现与 Rust 零依赖编译实现），无外部依赖、无 Runtime 绑定；
   - CI 与发布门禁必须由两个独立实现的校验器对 Standard 规范及元模式执行独立交叉验证；只有两个校验器的一致性判定达到 100% 时，方可允许构建进入发布阶段。
3. **带外公钥锚定与轮换机制（Out-of-Band Trust Anchor & Key Rotation）**：
   - **澄清签名语义**：GPG 签名能够证明发布包来自持有相应私钥的发布者（证明来源真实性与防篡改），但不自动证明规范本身的数学无错性；
   - 初始信任公钥指纹必须通过带外（Out-of-Band）独立渠道分发与公证锚定（如官方安全发布页、不可篡改证书透明度日志）；公钥轮换与吊销遵循严格的证书吊销列表（CRL）与 M-of-N 多签治理策略。
4. **官方标准测试向量独立多源维护与冲突裁决（Golden Test Vectors & Errata）**：
   - 官方标准测试向量（Golden Test Vectors）由跨组织规范工作组在独立的 Git 仓库中单独版本化维护，与任何具体的 Runtime 代码库解耦；
   - 当 Standard 规范与测试向量产生歧义或冲突时，由五权架构仲裁委员会发起形式化评审并发布勘误（Errata），在此之前遵循 Fail-Closed 原则暂停该特性的合规认证。
5. **完全确定性的可复现构建（Deterministic Reproducible Builds）**：Conformance Suite 校验器构建流程完全封闭可复现（Hermetic），任何人均可根据源码复现完全一致的二进制制品与物理 SHA-256 哈希指纹。
6. **六维兼容矩阵实测有效原则**：
   - 兼容矩阵中声明的向后兼容（例如 Runtime 2.1 支持 Standard 2.0），明确是指 Runtime 2.1 运行时向下兼容执行 Standard 2.0 规范；
   - 任何兼容性声明必须以 Conformance Suite 在 CI 中实际运行通过的组合为准，严禁仅凭 Manifest 声明而未经实测通过就认定兼容。

#### 产品六维版本兼容矩阵（Six-Dimensional Compatibility Matrix）

明确多维版本绑定关系，严格区分**草案标识（Draft ID）**与**正式发行版本（Release SemVer）**：

| Standard 版本 | Schema 契约版本 | Runtime 支持版本 | Adapter 兼容能力集 | Conformance Suite | Agent Eval 数据集 | 兼容策略与迁移说明 |
|---|---|---|---|---|---|---|
| **2.0.0** (正式) | `v2.0` (正式发行) | `2.0.0`+ (实测兼容) | `v2.0` (Class A/B 幂等) | `v2.0.0` (绑定 2.0.0 信任根) | `eval-2026.10` (独立版本) | 基础正式发行版，严格向下兼容所有 2.0.x 补丁 |
| **2.0.x-draft** | `draft-2026-10-31` | `2.0.0-alpha` ~ `beta` | 试验性 Adapter | `v2.0-draft` | 内部试验评测集 | 开发草案标识，禁止用于生产合规认证 |
| **2.1.0** (规划) | `v2.1` | `2.1.0`+ (运行时兼容 2.0) | `v2.1` (支持 Outbox CDC) | `v2.1.0` (兼容 2.0 套件) | `eval-2027.01` | 保持五权核心契约不变，向下兼容 2.0.x |

兼容性与显式声明铁律：
- **强制 Manifest 显式声明**：Reference Runtime 与 Adapter 必须在 Manifest 中显式声明所支持的规范版本与能力集，例如：
  ```json
  {
    "supported_standard_versions": ["2.0.0"],
    "declared_capabilities": ["class_a_idempotency", "windows_job_containment", "transactional_outbox"],
    "schema_version": "v2.0"
  }
  ```
- **不兼容组合硬拦截**：系统启动初始化时严格校验上述六维矩阵；任何未声明的组合直接抛出 `INCOMPATIBLE_VERSION_COMBINATION` 并拒绝加载，严禁静默空转或隐式降级。
- **核心契约中立**：核心协议严禁引入单一商业大模型 Provider 的私有字段或非标调用。

## 10. FPF 2.0 稳定版验收标准（架构基线冻结指标）

只有同时满足以下条件，才可以对外声明 FPF 2.0 Stable：

1. 五权治理原则、核心状态机、事件因果模型（含 UUIDv7 局部时间排序、sequence 严格单调递增、原生条件更新原子 CAS、Transactional Outbox 发件箱与 `PROJECTION_ONLY` 回放零副作用）和数据契约形成正式规范。
2. 治理后端、Agent Provider、Runner、Tool Gateway 和 Evidence Store 均有稳定接口与确定性契约测试。
3. GitHub 参考后端完成授权、任务、Review（严格绑定 Commit SHA）、Artifact 和生命周期全链路验证。
4. 落地正式的**对账与恢复协议（Reconciliation Protocol）**，支持 Provider 三级分级（Class A/B/C）、显式幂等作用域与并发去重语义、60 秒带抖动探针退避决水机制，严格执行 `NOT_FOUND ≠ PROVEN_NOT_EXECUTED` 延迟窗口校验，在崩溃恢复时**杜绝盲目重发**；远端执行子状态具备两层结构，`REMOTE_RUNNING` 严格执行恢复观测而非重新派发。
5. Local Worktree（Windows 11 原生生产级一级支持）与 Docker Sandbox 均完成生产级实机执行与崩溃恢复验证。
6. Windows 11 原生环境落实严格受控威胁模型：DEV/QA 独立操作系统账户、源码只读 ACL 硬防护、Credential Broker 命名管道 ACL 认证与短期令牌代理、`CREATE_SUSPENDED` 挂起启动绑定防逃逸、以及 Windows 本地防火墙默认拒绝出站规则阻断网络旁路。
7. 任务状态只能由可信事实和确定性 Reducer 推进，治理生命周期完备支持全局 `REVOKED` 立即中断、`HUMAN_RESOLUTION_REQUIRED` 正式状态与人工裁决、`INVALID_TEST` 独立环境重试预算、`QA_FAILED`（绑定失败制品与计数）、纠偏后的 `HUMAN_REJECTED` 归档分支及 `ROLLBACK` 等全异常跃迁。
8. Evidence Engine 基于五维证据模型（Provenance、Reproducibility、Isolation、Independence、Coverage）与 Profile 量化门槛矩阵（100% 测试成功率、100% 验收覆盖率、Release Profile 三主体防兼任铁律）验证来源、完整性与验收覆盖。
9. **FPF Conformance Suite** 具备基于声明能力集（Declared Capabilities）的确定性硬门禁判定能力，确立零依赖基础校验器与黄金测试向量信任根，并与概率性 **Agent Evaluation** 严格分轨，独立出具报告。
10. Bootstrap 能在干净的第三方仓库完成初始化，并通过 Doctor 和 Conformance 验收。
11. Windows 11 与 Ubuntu 的跨平台兼容矩阵均有对应实机测试记录（路径规范、进程树回收、权限映射、防火墙规则）。
12. FPF Standard、Reference Runtime 与 Conformance 三大产品双向验证体系及 Standard × Schema × Runtime × Adapter × Conformance × Eval Dataset 六维版本兼容矩阵完全清晰一致。
13. 合并和部署的最终决策权始终由人类保留，无凭据泄露或自动化旁路。

## 11. 优先级与依赖关系

| 优先级 | 工作项 | 依赖 | 结果 |
|---|---|---|---|
| P0 | 2.0 架构和规范边界 | 当前 main 能力盘点 | 统一目标与模块职责 |
| P0 | 核心契约、事件和 Reducer | 阶段0 | 稳定的协议内核 |
| P0 | Runtime / Dispatch 状态互操作 | 核心契约 | 避免双状态机和状态漂移 |
| P1 | Control Plane 真实端到端闭环 | Reducer、GitHub Adapter | 可靠协调与恢复 |
| P1 | Docker Runner、Tool Gateway、Credential Broker | Execution API、Policy | 可移植安全执行 |
| P1 | Evidence Engine、Conformance Kit | 事件和执行契约 | 可验证交付 |
| P1 | Bootstrap 2.0、兼容矩阵 | 核心契约、Adapter | 第三方项目接入 |
| P2 | GitLab 等其他治理后端 | GovernanceBackend 稳定 | 平台可移植 |
| P2 | 托管 Runner、多机调度 | Runner / Control Plane 稳定 | 组织级并发 |
| P2 | Production Feedback Loop | 2.0 Stable | 持续工程扩展 |
| P0 | G2 宪制强制力落地（`PLAN_ONLY`） | G3 身份模型、H1 项目边界 | 平台/密码学强制门禁 |
| P0 | G3 凭据与身份边界（`PLAN_ONLY`） | G2 | 仓库与工作区零静态密钥 |
| P0 | G4 状态机归约接入（`PLAN_ONLY`） | G3、§4.1 对账协议 | 事件驱动状态投影 |
| P1 | H1 项目注册与控制面隔离（`PLAN_ONLY`） | 阶段 1 Project Manifest | 项目边界可校验 |
| P1 | H2 worktree 生命周期（`PLAN_ONLY`） | G4 merge 事件、阶段 3 Runner | 工位可标记、可回收 |
| P1 | H3 部署就绪门禁（`PLAN_ONLY`） | G4、阶段 4 Evidence | 部署前 smoke 与迁移断言 |
| P0/P1 | H4 范围修正协议（`PLAN_ONLY`） | 阶段 1 Scope Grant | 越界必须事前授权 |

实施时允许并行开发，但接口和验收依赖必须先确定。不得以并行开发为理由，让多个模块分别定义任务状态、证据字段和授权语义。

---

## 12. 关键度量指标

FPF 的演进不以 Agent 数量、Prompt 数量、模型调用次数或自动化脚本数量作为主要指标。

建议跟踪：

| 指标 | 目标含义 |
|---|---|
| 新项目接入时间 | 从干净仓库到通过 Bootstrap / Conformance 的耗时 |
| Adapter 替换成本 | 更换模型、Runner 或后端时需要修改的核心代码范围 |
| 未授权动作阻断率 | 对预设越权测试，策略是否稳定拒绝 |
| 状态一致性 | 本地账本、远端事实和 Reducer 结果是否可解释、一致 |
| 恢复正确率 | 进程中断后能否恢复且不重复执行外部副作用 |
| 证据有效率 | 证据是否完整、真实、绑定正确 SHA 和验收条件 |
| 独立 QA 可信度 | QA 主体、执行环境和 Artifact 是否真实独立 |
| Conformance 通过率 | 项目和适配器是否满足规范要求 |
| Agent 规范遵循率 | 新 Agent 能否理解项目并遵守权限边界 |
| 单任务成本 | Token、Runner、存储和外部服务的可追踪成本 |

所有指标必须基于可复算的数据，不允许由 Agent 自评替代。

---

## 13. 风险与架构决策约束

1. **不提前分布式化。** SQLite 账本和单机 Runner 在当前阶段可以保留；是否升级数据库、队列和多机调度，应由真实并发、可用性和恢复指标决定。
2. **不把模型会话当作事实源。** 对话上下文只是执行输入，任务授权和正式状态必须落在可验证的规范记录中。
3. **不把 GitHub 永久写死在核心内核。** 先以 GitHub 为参考后端，抽象接口；其他平台必须通过符合性测试。
4. **不把 Transport 回执当作任务结果。** 发送成功、页面可见和任务完成是不同事实。
5. **不把文件隔离等同于安全隔离。** Worktree 是版本隔离手段，不天然构成操作系统、凭据和网络隔离。
6. **不让 QA 与 DEV 共享写权限。** QA 对被测版本只读，证据由独立主体和独立 Runner 生成。
7. **不以功能数量衡量成熟度。** 每个新增能力都必须有契约、权限边界、失败语义、恢复路径和符合性测试。
8. **不一次性重构所有包。** 先稳定模块职责和契约，再按兼容策略逐步拆分或迁移。

---

## 14. 近期执行顺序

建议按以下顺序进入后续正式研发，不在本路线图 PR 中直接实施代码变更：

1. **先完成阶段0：** 评审并冻结 FPF 2.0 架构边界、模块职责和核心契约草案。
2. **复审 Issue #61 / PR #62：** 以当前 main 为基线重新核查，确认 Dispatch 与 Runtime 的状态、事件、账本和授权语义，补足真实 Provider Smoke 和独立 QA。
3. **建立 Core Contract RFC：** 明确 Event Envelope、Task ID、Request ID、Attempt ID、Scope Grant、Execution Envelope 和 Evidence Manifest。
4. **完成 Evidence 语义与符合性设计：** 先解决“什么证据能够证明什么”，再扩展自动执行范围。
5. **实现 ExecutionBackend 与 Docker Sandbox：** 在不改变五权治理内核的前提下，验证真实隔离和资源控制。
6. **形成 Conformance Kit：** 将规范遵循、适配器验证和 Agent Friendliness 测试做成可独立运行的工具。
7. **最后推进 Bootstrap 2.0 与发行：** 让外部项目能够独立安装、初始化、升级和验证。

每个研发阶段必须单独建立 WORK_ORDER，明确允许路径、验收条件、停止条件和独立 QA 要求。路线图本身不构成对后续代码实现的概括性授权。

---

## 15. 结论

FPF 的长期价值不在于它能调度多少 Agent，而在于它能否把可信的软件工程协作变成一套跨项目、跨模型、跨平台、跨执行环境的标准能力。

因此，FPF 2.0 的建设重点应当从“继续增强当前自动化流程”转向：

- 把五权治理原则固化为规范；
- 把状态、授权和证据固化为稳定契约；
- 把模型、工具、Runner 和代码托管平台变成可替换适配器；
- 把执行隔离、凭据控制和恢复机制变成可复用 Runtime；
- 把符合性测试变成第三方接入和版本发布的必经门槛。

**最终目标：任何一个符合 FPF 规范的项目，都可以在不依赖特定模型、特定对话线程或特定开发者个人经验的情况下，建立一套可验证、可执行、可审计、可持续演进的 Agent 原生软件工程体系。**

这才是 FPF 从项目内工具走向标准化基础设施的标志。

---

## 附录 A · AEC 已交付能力 → FPF 2.0 六平面映射

> **用途：** 消除 AEC 五层架构与 2.0 六平面的口径冲突，回答“哪些已有实物可直接复用、哪些只是设计、哪些必须重做”。
> **事实来源：** `docs/architecture/FPF-AUTONOMOUS-ENGINEERING-COORDINATOR.md`、`docs/reports/FPF-AEC-DELIVERY-REPORT.md`、`docs/coordination/project-map.md`、本仓库 `packages/` 与 `tests/`、PR #69–#76 的合并记录。
> **时点：** 2026-11-11，main @ `9d96b37`。

### A.1 AEC 五层架构与 2.0 六平面的对应关系

本路线图 §3 的“六平面”指：Protocol & Conformance Foundation、Governance Plane、Control Plane、Execution Plane、Evidence & Assurance Plane、Integration Plane；Project Context / Observability / Agent Evaluation 为横向能力。

| AEC 五层（实现视角） | FPF 2.0 对应层 | 对应关系 | 差异 |
|---|---|---|---|
| A. Authority Plane（ScopeGrant、Baseline、凭据 Broker、人工门禁） | Governance Plane + Protocol Foundation | 授权、主体、角色、拒绝原因归 Governance；ScopeGrant/Baseline 的字段与版本归 Protocol | AEC 把“契约”隐含在实现里，2.0 要求独立版本化 Schema 与拒绝原因枚举 |
| B. Orchestration Plane（Daemon、Heartbeat、状态机、并发/熔断） | Control Plane | 一对一 | AEC 已有 24 状态机与 CAS journal，但没有事件源接入（G4） |
| C. Execution Plane（Provider Registry、ChatGPT Web、Codex DEV/QA） | Execution Plane + Integration Plane | 执行隔离归 Execution；Provider/后端适配归 Integration | AEC 的适配器契约可复用；真实在线会话仍 `NOT_RUN` |
| D. Evidence Plane（EVID、SHA-256、Artifact、裁决对账） | Evidence & Assurance Plane | 一对一 | AEC 的 `qa_artifact`/`qa_collector` 是实物；五维证据模型尚未落成独立 Verifier |
| E. Canonical State Plane（GitHub SSOT + 本地 SQLite Journal） | Governance Plane / Integration Plane + Control Plane | 远端正式事实归 Governance/Integration；本地 journal 归 Control Plane | AEC 把“权威事实”与“本地索引”画在同一层；2.0 明确二者不得混为同一权威源（§4.1） |
| （无） | Protocol & Conformance Foundation | AEC 只有架构文档与 e2e 测试，没有独立 Conformance Suite | 2.0 新增；属于缺口，不是重复建设 |
| （无） | 横向：Project Context / Observability / Agent Evaluation | AEC 有 Context 片段与成本预算，但没有项目注册表、统一观测与模型评测 | 2.0 新增；H1 与阶段 4 承接 |

**口径结论：** AEC 五层是“单项目、单后端、实现导向”的架构；2.0 六平面是“多项目、多后端、标准导向”的架构。二者不是替代关系，AEC 的 B/C/D 三层可直接映射并复用；A 与 E 需要按 2.0 的“协议/治理/集成”拆分；Protocol Foundation 与横向能力是 AEC 未覆盖的新增面。

### A.2 AEC Phase A–G 逐条产出物映射

| 阶段 | 产出物（仓库内实物） | PR / 合并 SHA | 六平面落点 | 状态 | 复用结论 |
|---|---|---|---|---|---|
| **Phase A** 架构契约 | `docs/architecture/FPF-AUTONOMOUS-ENGINEERING-COORDINATOR.md`；Issue #68 分阶段规划 | PR #69 / `2327ac1f3641` | Protocol Foundation（设计）+ Governance（五权）+ Control（状态定义） | 仅设计 | 作为历史设计输入复用；实现口径以 2.0 路线图为准 |
| **Phase B** 协调内核 | `packages/fpf_coordinator/dispatch/{states,core,journal}.py`；`tests/test_coordinator_kernel.py` | PR #70 / `ad7e904ad33f` | Control Plane | 已有实物（库） | 直接复用 24 状态机与 CAS journal；补事件源（G4） |
| **Phase C** Provider 适配器 | `packages/fpf_runtime/adapters/{base,chatgpt_web,codex_worker,registry,smoke}.py`；`browser_transport/transport.py`；`tests/test_provider_adapters.py` | PR #71 / `96b38d0f5765` | Execution + Integration | 部分实物（契约/Mock 已测，真实会话 `NOT_RUN`） | 复用接口与注册表；真实登录态会话需另立切片验证 |
| **Phase D** QA 证据闭环 | `packages/fpf_policy/{pr_gate,qa_artifact}.py`；`tests/test_qa_evidence_pipeline.py` | PR #72 / `437d6dd24fd6` | Evidence & Assurance + Governance | 已有实物 | 直接复用 `validate-card` 的独立 Review + Artifact 校验；补五维 Verifier |
| **Phase E** 安全与隔离 | `packages/fpf_runtime/security/{credential_broker,env_sanitizer,windows_isolation}.py`；`hook_guard_dev.py` | PR #73 / `15e0c1772248` | Execution（隔离）+ Governance（凭据） | 部分实物（抽象/单测；WFP 内核驱动 `NOT_RUN`） | 复用 Broker/净化器骨架；实机 ACL/WFP 需阶段 3 验证 |
| **Phase F** 守护与恢复 | `packages/fpf_runtime/daemon/{config,reconciliation,scheduler,server}.py`；`tests/test_daemon_reconciliation.py` | PR #74 / `2ef69643efd4` | Control Plane | 部分实物（单机骨架；跨机/长期运行 `NOT_RUN`） | 复用对账骨架；接 G4 事件与租约实机测试 |
| **Phase G** Golden Path | `tests/test_golden_path_e2e.py`；`docs/reports/FPF-AEC-DELIVERY-REPORT.md` | PR #75 / `bac0088055d8` | Evidence + Control（端到端） | 已有实物（模拟链路） | 复用为回归基线；不得当作真实外部 Provider 验收 |

> 说明：Phase G 的交付报告自身列明三项 `NOT_RUN`：WFP 内核驱动实机安装、真实 ChatGPT 在线长会话、多操作系统本地实机交叉运行。本表沿用该边界，不把 e2e 模拟升级为“真实集成已完成”。

### A.3 结论：复用、补齐、不要重做

**可直接复用（不重写）：**

1. `packages/fpf_coordinator/dispatch/` 的 24 状态定义、纯函数归约与 CAS journal——2.0 的 Control Plane 内核直接采用。
2. `packages/fpf_policy/{pr_gate,qa_artifact,qa_collector}.py` 的“独立身份 Review + Artifact 绑定 SHA”校验链——2.0 的 Evidence 门禁直接采用。
3. `packages/fpf_gates/hook_guard_dev.py` 与 `pre_handoff.py` 的本地快速拦截。
4. `packages/fpf_runtime/daemon/` 的调度、heartbeat、崩溃对账骨架。
5. `tests/test_golden_path_e2e.py` 的正向/返工/熔断三条链路，作为 2.0 回归基线。

**必须补齐（AEC 未交付）：**

1. GitHub 事件源与状态投影（G4）——把已有状态机接上真实事件，而不是再写一套状态机。
2. 项目注册表与控制面隔离（H1）。
3. worktree 标记、三条件判定与 TTL 回收（H2）。
4. 部署就绪门禁与迁移版本断言（H3）。
5. `SCOPE_AMEND` 范围修正协议（H4）。
6. 平台/密码学级强制力与密钥轮换（G2、G3）。
7. 独立 Conformance Suite、版本兼容矩阵、Project Context / Observability / Agent Evaluation 横向能力（§3、§9、阶段 4）。

**明确不要重做：**

1. 不新写第二套任务状态机；G4 只做事件接入与投影。
2. 不另建第二套 QA 证据校验器；H3 复用现有 Evidence Envelope 与 Artifact 校验。
3. 不重新实现 Provider 适配器骨架；真实会话验证是“补验证”，不是“重写接口”。
4. 不把 AEC 的历史文档当成现行规范；其正文保持原样，仅以状态横幅降级（见 `docs/architecture/FPF-AUTONOMOUS-ENGINEERING-COORDINATOR.md` 顶部）。
