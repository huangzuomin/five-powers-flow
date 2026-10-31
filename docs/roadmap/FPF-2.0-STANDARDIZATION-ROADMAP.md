# FPF 2.0 标准化能力建设与迭代路线图

> **文档版本：** v0.1（架构规划提案）  
> **编制日期：** 2026-10-31  
> **基线：** main @ d2852c9315f76010a1dcb752229cec54d397eeed  
> **关联工作令：** [Issue #66](https://github.com/huangzuomin/five-powers-flow/issues/66)  
> **文档性质：** 架构规划，不替代现行 FPF-RFC-001，不构成任何代码、合并、发布或部署授权。

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

## 2. 当前基线与能力边界（截至 2026-10-31）

路线图以当前 main 为事实基线。必须区分已合并能力、Draft 实验能力和尚未验证能力，不能将设计、接口或模拟测试表述为真实集成。

### 2.1 当前 main 已具备的能力

当前 main 基线为 d2852c9，最近一次合并为 PR #65。

| 模块 | 当前能力 | 当前定位 |
|---|---|---|
| FPF-RFC-001 | 五权治理、角色职责、交接卡、证据与生命周期规范 | 规范基线 v1.2.1 |
| schemas | WORK_ORDER、DEV_HANDOFF、QA_RESULT、证据清单等结构化契约 | 协议数据契约 |
| fpf_policy | 受保护路径、策略判断、PR 类型与治理边界 | 共享策略层 |
| fpf_gates | 提测前本地门禁、工作区与路径检查 | 本地强制检查 |
| fpf_coordinator | 卡片解析、Git SHA、Diff、证据清单和生命周期校验 | 确定性裁决参考实现 |
| fpf_runtime | Agents SDK 与 Codex CLI 的单切片 DEV/QA 执行、独立 Worktree、有界返工和本地 Ledger | Runtime 0.2 参考实现 |
| fpf_bootstrap | 项目发现、初始化计划、治理产物、工位创建和 Doctor 检查 | Bootstrap 0.3 参考实现 |
| GitHub Actions | Schema、边界测试、独立 QA 证据采集和服务端门禁 | GitHub 参考后端 |

补充说明：

- Runtime 0.2 使用本地 SQLite Ledger 保存执行过程。该账本是运行时操作记录，不应取代 GitHub 上的授权、PR、Review、Commit 和正式验收事实。
- 当前证据 Profile 已按任务类型区分，不应将“32项证据规范”理解为每个任务都必须机械执行全部32项。
- PR #65 已增强对既有治理文件的保留、Bootstrap 韧性和凭据保护。

### 2.2 Draft PR 中的实验能力

| 事项 | 当前状态 | 路线图处置 |
|---|---|---|
| Issue #61 / Draft PR #62 角色派发与恢复 | 实验性实现，尚未进入 main | 纳入控制平面演进，但须先完成主干集成审查、真实 Provider Smoke 和独立 QA |
| Codex Thread Bridge | 已定义可插拔 Driver 契约，真实写入与读取尚未完成 | 作为可选 Transport Adapter，不作为核心依赖 |
| ChatGPT Web Transport | 已定义接口，真实登录态浏览器发送、可见性和回复读取尚未完成 | 作为可选适配器，必须单独验证 |
| 有界协调循环 | 已有前台循环设计，不等于长期 Daemon 或托管调度 | 后续按可靠性需求演进 |
| Issue #63 / PR #64 接力演练 | 文档流程演练，有独立 QA 审查记录；仍为 Draft | 作为流程验证参考，不视为 Runtime 产品能力 |

### 2.3 尚未验证或尚未形成标准能力的事项

- 真实 Codex Desktop 线程桥的发送、回执、执行状态、结果读取和恢复。
- 真实已认证浏览器对指定 ChatGPT 会话的发送与回复核验。
- Windows 11 实机环境下的完整运行、崩溃恢复和并发验证。
- 长期运行的调度器、跨机器 Runner 和可靠任务队列。
- DEV 与 QA 在操作系统账户、文件系统、凭据和网络层面的完整隔离。
- 统一的跨 Provider、跨 Runner 证据契约与符合性测试。
- 面向第三方项目的标准化安装、升级、兼容性和认证流程。

上述能力均应保持 NOT_RUN、EXPERIMENTAL 或 PLANNED 状态，直到有固定版本、真实环境和可复核证据。

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

#### 1. Reconciliation 状态机与远端事实子状态（F-03）

| 状态 | 判定语义 | 允许的系统动作 | 映射远端事实子状态 |
|---|---|---|---|
| `REMOTE_CONFIRMED` | 权威远端已确认对应对象与事实存在 | 以远端事实为准，更新本地账本并恢复调度推进 | `REMOTE_ACCEPTED`（已接收待分配）<br>`REMOTE_RUNNING`（执行中）<br>`REMOTE_TERMINAL`（终态回执已生成） |
| `LOCAL_PENDING` | 本地已记录执行意图，远端尚未确认但仍处于轮询窗口内 | 继续对远端执行幂等核验，禁止推进后续状态 | `REMOTE_UNSEEN` |
| `UNKNOWN_OUTCOME` | 外部副作用发送结果未知（已发出未回执/网络中断/进程崩溃） | **严禁盲目重发**；保持当前任务阻断，启动专有探针核实外部真实状态 | `REMOTE_UNKNOWN` |
| `REMOTE_CONFLICT` | 本地执行记录与权威远端事实冲突（如未授权 SHA 漂移或越权修改） | 立即暂停推进，触发告警并冻结当前工单 | `STATE_DIVERGED` |
| `REMOTE_UNAVAILABLE` | 权威治理后端（如 GitHub API）离线或鉴权失效 | 系统 Fail-Closed 阻断，保持本地意图只读，等待连通性恢复 | `BACKEND_OFFLINE` |
| `HUMAN_RESOLUTION_REQUIRED` | 存在不可逆状态分歧、探针超时或自动裁决不可达 | 终止自动重试，持久化分歧凭证，升级人类负责人手工裁定 | `ESCALATED_TO_HUMAN` |

#### 2. Agent Provider 幂等能力三级分级模型与硬性防重约束（F-01 & F-02）

由于外部大模型 Provider 与执行引擎的实现差异，系统不得假设所有 Provider 均具备原生幂等性，必须按能力分级施加恢复策略：

| 能力等级 | Provider 特征 | 适用系统恢复策略与硬性防重约束 |
|---|---|---|
| **Class A（原生幂等）** | 原生支持 `idempotency_key` 过滤 | 允许自动重发，但**必须同时满足三要素**：<br>1. 重发使用原始 `idempotency_key`；<br>2. 请求体标准规范化摘要 `canonical_payload_digest` 必须 100% 严格一致（Key 相同但 Payload 改变时 Provider 必须抛出 `IDEMPOTENCY_CONFLICT` 拒绝）；<br>3. 处于 Provider 声明的有效保留期（Retention Period，如 24 小时）内。 |
| **Class B（可查不可防重）** | 不支持请求去重，但提供任务查询接口（可查 Request ID 历史） | **严禁直接重发**；明确铁律 **`NOT_FOUND ≠ PROVEN_NOT_EXECUTED`**。<br>受最终一致性延迟影响，只有在 Provider 声明的**最大可见性延迟窗口（Visibility Delay Window，如 30 秒）**过后再次查询仍为 `NOT_FOUND`，或 Provider 官方承诺强一致性查询时，方可裁决为“未执行并安全重发”；否则必须保持 `UNKNOWN_OUTCOME`。 |
| **Class C（无查询无幂等）** | 既不支持去重也不提供可信执行历史查询接口 | 发生未知中断时一律强制置为 `UNKNOWN_OUTCOME`，**绝对禁止自动重发**，仅允许保存现场证据并升级人类接入。 |

#### 3. 探针恢复算法与超时退避预算（Probe Recovery Algorithm）

针对 `UNKNOWN_OUTCOME` 状态，控制平面必须启动受限只读探针：
- **只读零副作用契约**：探针仅调用只读查询接口（如 `check_status`、`query_request_receipt`），严禁触发任何产生新任务的写操作。
- **指数退避与抖动预算**：探测间隔按 2s、4s、8s、16s 指数退避并加入随机抖动（Jitter，±20%），最大单次请求超时 5s，总探测超时预算硬性设定为 60 秒。
- **决水与超时升级**：
  - 若在预算时间内探针核实任务已成功接收并生成回执，状态平滑跃迁至 `REMOTE_CONFIRMED`（细化为 `REMOTE_ACCEPTED` 或 `REMOTE_RUNNING`）；
  - 若经过完整可见性延迟窗口后探针核实任务确未被外部接收，状态置为 `LOCAL_PENDING` 并安全重新派发；
  - 若超过 60 秒依然无法确定外部副作用结果，立即强制跃迁至 `HUMAN_RESOLUTION_REQUIRED`，冻结任务推进，杜绝无限悬挂。

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
- `event_type`：规范化事件类型枚举。
- `aggregate_id` 与 `aggregate_version`：定义状态聚合根标识及其单调递增版本号，依托权威存储的原子 CAS 实现并发冲突仲裁。
- `task_id`、`request_id`、`attempt_id`：任务层级、请求意图和单次尝试执行标识。
- `causation_id`：导致本事件产生的直接上游事件 ID，形成可追溯的因果依赖有向无环图（DAG）。
- `correlation_id` / `idempotency_key`：跨系统分布式追踪根标识与防重派发键。
- `sequence`：同一聚合根内由权威写入机制分配的严格递增自然数序列号。
- `occurred_at`：事件在客户端或执行主体产生的时间戳（仅作观测参考，不可作为权威逻辑排序基准）。
- `recorded_at`：权威账本接收并持久化落盘的时间戳。
- `actor` / `principal`：真实操作主体（人类账号或 Agent 真实身份及版本）。
- `role` / `action`：主体当前生效角色及申请执行的规范动作。
- `source_adapter`：事件来源适配器及环境标识。
- `object_refs`：Commit SHA、PR Number、Workflow Run ID、Artifact SHA 等外部权威引用。
- `payload_digest`：事件载荷的 SHA-256 哈希摘要，保障事件防篡改。
- `replay_policy`：事件回放策略枚举（`PROJECTION_ONLY` 为强制默认策略，运行时物理阻断外部副作用）。

#### 原子 CAS 与 Transactional Outbox 事务契约（F-06）

为彻底消除“数据库版本已提交但事件发布失败导致下游丢事件”或“事件已发布但数据库事务回滚导致幻读消费”的双写不一致故障窗口，事件引擎必须实现 Transactional Outbox 契约：

```
BEGIN TRANSACTION;
  -- 1. 原子 CAS 并发校验
  SELECT aggregate_version FROM task_aggregates WHERE aggregate_id = :agg_id;
  IF current_version != expected_version THEN
    ROLLBACK; -- 触发对账与恢复协议 (Reconciliation)
  END IF;

  -- 2. 写入事件流水并原子递增聚合版本
  INSERT INTO task_events (event_id, aggregate_id, sequence, payload, ...);
  UPDATE task_aggregates SET aggregate_version = aggregate_version + 1;

  -- 3. 同一本地事务中写入 Outbox 发件箱表
  INSERT INTO transactional_outbox (outbox_id, event_id, destination, status, created_at);
COMMIT;

-- 4. 异步 Outbox Dispatcher
Outbox Dispatcher 守护进程 (CDC 或定时轮询) ──> 保证 At-Least-Once 投递至事件总线
       ↓
-- 5. 下游幂等消费
下游订阅者按 event_id 进行幂等表去重消费 ──> 回写 Outbox 确认完成
```

#### 事件回放（Event Replay）与外部副作用绝对物理隔离铁律

必须严格区分**事件回放（Event Replay）**与**命令重执行（Command Re-execution）**：
1. **事件回放（Event Replay）**：仅用于系统冷启动、灾备重建、内存投影更新或本地审查。回放期间的 `replay_policy` 必须为 `PROJECTION_ONLY`。在运行时层面，系统底层的网络适配器、Tool Gateway、GitHub API 客户端与 Agent Provider 必须被**硬性切断或替换为 NullMock**，**绝对禁止产生任何外部网络请求、写操作或模型调用**。
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

FPF 的核心目标是统一治理协议，而不是强制所有执行环境采用单一技术实现。FPF 主研发机与开发者工作站广泛运行在 Windows 11 原生环境，涉及 Windows 专有工具链、NTFS 权限及本地桌面交互。追求架构规范绝不能以牺牲 Windows 11 原生环境的实际可用性为代价。同时，原生兼容性必须建立在严谨的威胁模型与受控权限契约之上，杜绝虚假的安全绝对化承诺。

2.0 确立**三层执行后端架构（Three-Tier Execution Architecture）**：

1. **第一层：Local Worktree Runtime（生产级一级支持后端）**
   - **定位**：Windows 11 原生与 Linux 本地执行的生产级一级支持（First-Class Native Backend）。
   - **核心职责**：直接调用宿主机原生工具链（PowerShell 7+、Git CLI、Node、Python）、支持 Windows 专属软件与进程控制、提供零容器化开销的高性能本地开发体验。
   - **治理说明**：属于原生兼容执行后端，提供 Git 工作树版本隔离，安全边界由下述 OS 级契约约束。
2. **第二层：Docker Sandbox Runtime（标准化隔离执行后端）**
   - **定位**：可移植、可复现的标准化容器隔离环境，作为 FPF 2.0 标准化建设的优先隔离实现。
   - **核心职责**：Linux 容器化执行、统一依赖打包、隔离文件系统挂载、资源（CPU/内存）配额限制、网络出站白名单控制与确定性环境重置。
3. **第三层：Ephemeral VM Runtime（高风险强隔离后端）**
   - **定位**：面向不可信第三方代码、系统内核级修改或高危自动化操作的强安全后端，后续按需引入。

#### Windows 11 原生环境受控威胁模型与安全契约（F-04 & F-05）

针对宿主机同用户执行可能导致的权限混淆、凭据泄露及进程残留风险，Windows Local Worktree 必须执行以下受控契约：

1. **操作系统级身份隔离（OS Identity Separation）**：
   - 生产环境中，DEV Agent 与 QA Agent 必须运行在独立的非管理员 Windows 用户账户下（如 `fpf_dev_worker` 与 `fpf_qa_worker`）；
   - 禁止在特权管理员（Elevated Admin / UAC bypass）上下文运行 Agent 进程。
2. **源码只读 ACL 与外部证据存储（Read-Only ACL & External Storage）**：
   - 在 QA 任务启动时，系统通过 Windows NTFS ACL（如 `icacls`）将 DEV 工作树目录对 QA 账户显式标记为**严格只读（Read & Execute only）**，物理阻断 QA 修改被测代码的可能；
   - **外部证据存储契约**：QA 的测试产物与审计日志**强制重定向至工作区外独立的受保护凭据存储卷**，DEV 账户对此目录无修改权限，严禁 QA 在被测仓库工作树内直接获得写入权限。
3. **Credential Broker 临时令牌代理与内存生命周期（F-05）**：
   - Agent 进程严禁持有长期持久化密钥（如 GitHub PAT），仅由外部守护的 Credential Broker 按任务签发最短生存期（如 15 分钟）的临时作用域令牌；
   - 凭据优先通过命名管道或匿名 IPC 仅在调用瞬间按需传输，避免作为全局环境变量注入（防止子进程继承或写入 Crash Dump）；
   - 凭据代理在使用完毕后对持有敏感数据的固定字节缓冲区执行 `SecureZeroMemory`，最大程度减少内存驻留窗口；严禁凭据写入磁盘或日志。
4. **Windows Job Objects 进程树回收契约（F-04）**：
   - **消除绝对化承诺**：在受支持的 Windows 环境及既定威胁模型下，通过 Windows Job Objects 施加严格的进程生命周期管理；
   - **启动挂起绑定**：宿主使用 `CREATE_SUSPENDED` 标志创建初始进程，在将进程句柄显式分配给 Job Object 前禁止执行任何指令，杜绝加入前的逃逸竞态；
   - **句柄防继承与防脱离**：Job Handle 设置为不可继承（`bInheritHandle = FALSE`），显式配置 `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`，且不授予 `JOB_OBJECT_LIMIT_BREAKAWAY_OK` 策略，从内核层拦截 `CREATE_BREAKAWAY_FROM_JOB`；
   - **嵌套与终止验证**：支持 Windows 嵌套 Job 策略，确保终止信号逐级传递；该机制必须通过 Conformance Suite 中的专用进程树逃逸测试验证。
5. **Tool Gateway 全面接管（Tool Gateway Interception）**：
   - 严禁 Agent 自由调用未经白名单审计的 Windows 系统命令或自动化浏览器；所有文件写操作、网络请求与外部工具调用统一经由 Tool Gateway 策略引擎鉴权。

#### Windows 11 与 Linux (Ubuntu) 跨平台支持矩阵

| 验证维度 | Windows 11 原生环境 | Ubuntu / Linux 环境 | 跨平台兼容硬性约束 |
|---|---|---|---|
| **Local Worktree** | 生产级实机必测（NTFS、PowerShell 7+、Git Worktree、只读 ACL） | 生产级实机必测（ext4、Bash、Git Worktree、chmod 只读） | 保持两端治理命令契约一致，禁止硬编码类 Unix 专有路径语法 |
| **Docker Sandbox** | 生产级实测（WSL2 引擎 / Docker Desktop） | 生产级实测（原生 Docker Engine） | 规范 Linux 容器与 Windows 宿主机之间的路径映射与权限转换 |
| **文件系统与路径** | 兼容大小写不敏感、反斜杠/正斜杠兼容、NTFS 权限 | 大小写敏感、POSIX 权限模型、符号链接 | 核心协议内部全部使用规范化正斜杠 UTF-8 相对路径 |
| **进程与生命周期** | Windows Job Objects 进程树严格回收，防 breakaway 逃逸 | POSIX 进程组与 cgroups 资源回收 | 超时或取消时必须保证子进程树被完全清理 |
| **凭据与环境变量** | Broker 短期令牌 + 内存清零，严禁落盘被测目录 | POSIX 环境变量与临时 tmpfs 挂载 | 无论平台，敏感 Token 与私钥一律禁止落盘到被测目录 |
| **网络边界防护** | Windows 本地防火墙规则 / Tool Gateway 统一接管 | iptables / 容器网络命名空间隔离 | 未授权的外部 IP/端口调用必须 Fail-Closed |
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
“人类批准合并”是治理生命周期的状态跃迁，而不是技术证据的更高可信度。一个项目即使被人为合并，若其缺少独立测试凭据，其证据质量依然为零；反之，一个代码通过了严格独立 QA 认证的项目，即使人类决策暂缓合并，其证据可信度依然完备。将二者混淆在单条线性等级轴上属于概念错误。

FPF 2.0 确立**五维证据评估模型（Five Dimensions of Evidence Quality）**，建立可量化门槛，并与**完备的治理生命周期状态机**正交解耦：

#### 1. 五维证据评估模型（Evidence Quality Dimensions）

| 维度 | 核心核验问题 | 判定标准与防伪要求 |
|---|---|---|
| **Provenance（来源可信度）** | 证据由谁产生？来源是否经过平台签名与防篡改？ | 必须由平台认证的 Runner、采集器或独立主体签发，禁止接受不可追溯的匿名自由文本。 |
| **Reproducibility（可复现性）** | 外部复测时能否在固定环境下按相同输入和命令复现结果？ | 必须记录固定的基线与测试 SHA、完整命令行、环境变量指纹及依赖锁定清单。 |
| **Isolation（环境隔离度）** | 测试执行是否在有效隔离的受控环境中进行？ | 明确标识执行边界（非隔离本地进程、Git Worktree 目录隔离、Docker 容器隔离或独立 VM）。 |
| **Independence（主体独立性）** | 验证主体与被测开发主体是否严格分离？ | QA 主体与 DEV 主体必须身份正交，QA 对被测源码严格只读，证据写入独立外部存储。 |
| **Coverage（验收覆盖率）** | 证据产出是否完整覆盖对应工作令的所有验收条件？ | 证据集必须与工作令中的 acceptance_criteria 形成逐项映射，缺失项一律标记为 `NOT_RUN`。 |

#### 2. 任务风险驱动的量化证据门槛矩阵（F-08）

五维证据不计算主观平均分，按 Profile 实行严格可量化的逐维硬门禁：

| 任务 Profile | 测试执行成功率 | 验收条款覆盖率 | 路径/边界合规率 | 环境隔离要求 | 主体独立性要求 |
|---|---|---|---|---|---|
| **Docs Profile（文档/规范）** | 100% 链接可达/无格式错误 | 100% 逐条对应证据 | 100% 严格限定在 allowed_paths | Local Worktree | 独立平台 QA 审查 |
| **Library Profile（库/模块）** | 100% 单元测试通过 (0 Fail) | 100% 验收断言覆盖 | 100% 严格限定源码与测试路径 | Docker 或 Windows 只读 ACL | 独立 QA Runner |
| **Core Profile（内核/架构）** | 100% 回归测试通过 (0 Fail) | 100% 验收条款 + 核心路径分支覆盖 | 100% 无禁止路径修改 | 容器隔离或独立 OS 账户 | 独立 QA 主体 + Actions 物理 Artifact |
| **Release Profile（正式发布）** | 100% 全量套件与 E2E 绿灯 | 100% 覆盖全量功能矩阵 | 100% 零未提交/未跟踪文件 | 强隔离 VM 或受限预发实机 | 双独立主体签字 + 人类负责人授权 |

#### 3. 完备的治理生命周期状态机与全阶段异常迁移规则（F-07）

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
       │                                                      ├─[环境/命令无效]─> INVALID_TEST
       │                                                      ├─[依赖冲突]────> BLOCKED     │
       │                                                      │                    │        │
       │                                                      │                    ▼ (对账恢复)
       │                                                      │               DISPATCHED    │
       │                              ┌───────────────────────┴───────────────────────┐     │
       │                              ▼                                               ▼     │
       │                        QA_VERIFIED (PASS)                              QA_FAILED   │
       │                              │                                               │ (绑定失败制品与计数)
       │                              ▼                                               ▼     │
       │                        HUMAN_APPROVED ──> MERGED ──> RELEASED          DEV_REWORK_LOOP
       │                              │                 │
       │                              ├─[人类否决]        └─[线上故障回滚]
       │                              ▼                 ▼
       └───────────────────────> HUMAN_REJECTED        ROLLBACK
```

- **REVOKED 全局撤销契约**：在 `DISPATCHED`、`DEV_SUBMITTED` 或 `INDEPENDENT_QA_EVALUATING` 等任意活动状态下，若人类发出撤销指令、工作令被修改或基线发生漂移，状态立即强制跃迁至 `REVOKED`。系统必须同步回收临时凭据、清理执行工作区，并将该工单的未完成产物永久废弃。
- **BLOCKED 挂起与恢复规则**：进入 `BLOCKED` 后调度冻结。仅当对账协议决水成功或阻塞依赖解决后，生成 `UNBLOCKED` 事件恢复至 `DISPATCHED`。
- **INVALID_TEST 重测规则**：因环境故障或测试脚本自身错误导致中断，状态置为 `INVALID_TEST`，打回调度层重新配置环境并再次进入 `INDEPENDENT_QA_EVALUATING`，**不计入 DEV 代码返工次数**。
- **QA_FAILED 深度绑定与返工上限**：QA 判定失败必须绑定失败测试日志、固定测试 SHA 及递增的 attempt 计数。DEV 返工必须基于该失败证据包展开；若 attempt 超过工作令设定的重试上限（如 3 次），强制跃迁至 `HUMAN_RESOLUTION_REQUIRED`，防止无限返工死循环。
- **HUMAN_REJECTED 与 ROLLBACK 规范**：人类否决后工单归档；合并或发布后若发生线上故障，必须由人类独立授权签发 `ROLLBACK` 工作令，记录反向提交 SHA 与回滚验证证据。

#### 4. 向后兼容的执行记录标签（Historical Capture Tags）

为保持对现行工程记录的向后兼容，保留 T0～T3 作为底层执行证据采集标签，但其仅代表单次命令执行的捕获层级，不代表治理终态：
- **T0（Agent 自述）**：仅证明 Agent 声称执行过某操作，不具备任何客观验收证明力。
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

---

## 9. 五类资产、三大产品双向验证体系与版本兼容矩阵（F-09）

为明确 FPF 的商业与开源发行形态，FPF 将五类工程资产归入三大独立演进的正式产品线，并建立双向验证闭环：

```
                              ┌──────────────────────────────────────────────┐
                              │ 1. FPF Standard（五权治理标准库）              │
                              │    - 规范文档 (RFC)、JSON Schemas、事件契约   │
                              │    - 中立定义产品边界、权限模型与数据契约      │
                              └──────┬───────────────────────────────▲───────┘
                                     │                               │
                        规范遵循约束 │                               │ 独立验证元模式与规范自洽
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
│    - Conformance CLI、固定 Mock Provider、五维证据验证器、合规报告生成器     │
│    - 双向独立验证：既验证 Standard 规范自洽性，又验证 Runtime 实现合规性   │
│                                                                            │
│    [附属评测包] FPF Agent Evaluation Framework                              │
│    - 独立评测大模型在 Agent 提示词下的行为稳定性与可靠度统计指标           │
└────────────────────────────────────────────────────────────────────────────┘
```

#### 产品版本多维兼容矩阵（Multi-Dimensional Compatibility Matrix）

| Standard 版本 | 兼容的 Schema 版本 | 支持的 Runtime 版本 | 适用的 Conformance Suite | 兼容策略与迁移说明 |
|---|---|---|---|---|
| **2.0.x** | `draft-2026-10-31` / `v2.0` | `2.0.0-alpha` ~ `2.0.x` | `v2.0.x` | 基础标准基线，严格向下兼容所有 2.0.x 补丁版本 |
| **2.1.x** (规划) | `v2.1` | `2.1.0`+ (可向下兼容 2.0) | `v2.1.x` (兼容 2.0 套件) | 引入生产反馈扩展，保持核心五权与事件契约不变 |

兼容性铁律：
- **版本号相同不等于天然兼容**：Reference Runtime 发布包必须在 Manifest 中显式声明：`supported_standard_versions: ["2.0.0", "2.0.1"]`；未声明的版本一律拒绝初始化。
- **核心契约中立**：核心协议严禁引入单一商业 Provider 的私有字段或非标调用。
- **显式能力降级防护**：Adapter 未声明的能力调用必须直接抛出 `UNSUPPORTED_CAPABILITY` 异常，严禁静默空转。

## 10. FPF 2.0 稳定版验收标准（架构基线冻结指标）

只有同时满足以下条件，才可以对外声明 FPF 2.0 Stable：

1. 五权治理原则、核心状态机、事件因果模型（含 UUIDv7 时间排序、sequence 严格单调、原子 CAS 并发校验、Transactional Outbox 原子事务发件箱与 `PROJECTION_ONLY` 回放零副作用）和数据契约形成正式规范。
2. 治理后端、Agent Provider、Runner、Tool Gateway 和 Evidence Store 均有稳定接口与确定性契约测试。
3. GitHub 参考后端完成授权、任务、Review（严格绑定 Commit SHA）、Artifact 和生命周期全链路验证。
4. 落地正式的**对账与恢复协议（Reconciliation Protocol）**，支持 Provider 三级分级（Class A/B/C）、60 秒带抖动探针退避决水机制，严格执行 `NOT_FOUND ≠ PROVEN_NOT_EXECUTED` 延迟窗口，在崩溃恢复时**杜绝盲目重发**。
5. Local Worktree（Windows 11 原生生产级一级支持）与 Docker Sandbox 均完成生产级实机执行与崩溃恢复验证。
6. Windows 11 原生环境落实受控威胁模型：DEV/QA 独立操作系统账户、源码只读 ACL 硬防护、Credential Broker 短期令牌注入、DPAPI 内存清零及 Job Objects 进程防逃逸。
7. 任务状态只能由可信事实和确定性 Reducer 推进，治理生命周期完备支持全局 `REVOKED` 立即中断、`BLOCKED`、`INVALID_TEST`、`QA_FAILED`（绑定失败制品与计数）及 `ROLLBACK` 等全异常跃迁。
8. Evidence Engine 基于五维证据模型（Provenance、Reproducibility、Isolation、Independence、Coverage）与 Profile 量化门槛矩阵（100% 测试成功率、100% 验收覆盖率）验证来源、完整性与验收覆盖。
9. **FPF Conformance Suite** 具备基于声明能力集（Declared Capabilities）的确定性硬门禁判定能力，并与概率性 **Agent Evaluation** 严格分轨，独立出具报告。
10. Bootstrap 能在干净的第三方仓库完成初始化，并通过 Doctor 和 Conformance 验收。
11. Windows 11 与 Ubuntu 的跨平台兼容矩阵均有对应实机测试记录（路径规范、进程树回收、权限映射）。
12. FPF Standard、Reference Runtime 与 Conformance 三大产品双向验证体系及多维版本兼容矩阵完全清晰一致。
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
