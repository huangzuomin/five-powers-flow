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

### 4.1 状态账本与权威事实必须分开

Runtime Ledger 与 PR #62 中的 Dispatch Journal 不应简单合并，也不能各自演化成独立的权威状态源。

统一原则：

- GitHub 参考后端中的 Issue、PR、Review、Commit、Workflow 和 Artifact，承载该后端配置下的正式治理事实。
- Git Commit SHA 锚定代码版本。
- 经验证的 Artifact 和 QA Review 锚定独立验收事实。
- SQLite 等本地 Ledger 只记录执行意图、回执、轮询、重试和恢复过程。
- 本地账本丢失或与远端事实冲突时，必须重新读取权威后端并进行 Reconciliation，不能凭本地状态推进正式生命周期。

2.0 应统一 Task ID、Request ID、Attempt ID、Event ID、Correlation ID 和事件格式，但暂不要求统一底层数据库。只有在多 Runner、多实例和并发需求得到实测后，再决定是否引入 PostgreSQL 或消息队列。

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

### 5.1 统一事件信封

建议所有跨模块事件具有以下公共字段：

- event_id：全局唯一事件标识。
- event_type：事件类型。
- task_id、request_id、attempt_id：任务和执行关联标识。
- sequence：同一任务或请求内的顺序号。
- occurred_at：事件发生时间。
- actor / principal：真实执行主体。
- role / action：角色和执行动作。
- source_adapter：事件来源适配器。
- contract_version：契约版本。
- correlation_id / idempotency_key：关联和幂等控制。
- object_refs：Commit、PR、Artifact 等外部对象引用。
- payload_digest：事件内容摘要。

事件记录应追加写入，禁止用后续状态覆盖历史事实。状态是对经过验证事件的确定性归约结果，而不是 Agent 自由填写的字段。

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

### 6.1 Runner 演进顺序

| 后端 | 目标定位 | 迭代顺序 |
|---|---|---|
| Local Worktree | 当前本地参考执行环境 | 保留并完善 |
| Docker Sandbox | 可移植隔离执行 | 2.0 优先实现 |
| Ephemeral VM | 高风险任务、强隔离和临时环境 | 2.0 后续增强 |
| Persistent Runner | Windows 特殊环境、硬件依赖和长期服务 | 按真实需求接入 |
| Hosted / Multi-Runner | 多机并发和组织级调度 | 规模验证后再建设 |

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

### 7.2 证据可信等级

建议区分以下层级，避免把不同来源的结果混为一谈：

| 等级 | 来源 | 可证明事项 | 不可单独证明事项 |
|---|---|---|---|
| T0 | Agent 自述 | Agent 声称做过什么 | 实际执行、QA 通过 |
| T1 | 本地观察与日志 | 本地观察到的状态 | 日志来源真实性、独立性 |
| T2 | 可复跑的确定性测试 | 固定环境中的测试结果 | 独立主体和平台级认证 |
| T3 | 隔离 Runner 与完整 Artifact | 指定版本、环境和命令的执行证据 | 独立 QA 主体授权 |
| T4 | 平台认证的独立 QA Review + Artifact | 独立验收主体对固定 SHA 的正式结论 | 人类批准合并或部署 |
| T5 | 人类授权的 Merge / Release 记录 | 最终决策与发布事实 | 超出授权范围的其他操作 |

等级不能通过 Agent 自行声明提升，必须由可信验证器核验对应来源。

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

### 阶段 2：Control Plane 与可靠协调

**优先级：P0/P1｜2.0-alpha**

目标：让任务可以安全派发、观测、恢复和有界重试。

交付物：

1. 统一 Dispatcher、Scheduler、Reconciler 和任务队列接口。
2. 统一 Request ID、Attempt ID、Receipt 和 Observation。
3. 实现发送意图先持久化、幂等派发和未知结果恢复。
4. 统一 Runtime 与 Dispatch 的生命周期事件。
5. 建立并发锁、超时、取消、退避、熔断和人工接管机制。
6. 接入 GitHub 参考后端，形成可复核的完整任务状态流。

验收条件：

- 进程在派发前后、回执前后和轮询过程中中断，恢复后不会盲目重复发送。
- 状态推进必须重新读取并验证规范事实。
- QA FAIL 只能触发有界返工；QA PASS 只能到达人工合并门禁。
- 未确认的取消、未知回执和外部服务异常必须阻断并要求 Reconciliation。
- 至少完成一次真实 DEV → 独立 QA → FAIL → DEV 返工 → PASS → 人工合并门禁的端到端演练。

**当前关联：** Issue #61 / Draft PR #62。该项应先完成独立审查、主干基线集成和真实 Provider Smoke，不应仅因接口与离线测试通过就视为阶段完成。

### 阶段 3：Portable Execution Runtime

**优先级：P1｜2.0-beta**

目标：让 Agent、模型和执行环境可以替换，而不改变治理内核。

交付物：

1. AgentProvider 统一接口。
2. ExecutionBackend 统一接口。
3. Local Worktree 和 Docker Sandbox 两个首批 Runner。
4. Tool Gateway 和 Capability Profile。
5. Credential Broker 与临时凭据管理。
6. 任务级时间、Token、并发和费用预算。
7. Agent Session 的创建、恢复、取消和结果回传。
8. Windows 11 与 Ubuntu 的参考环境配置和实机验证记录。

验收条件：

- 同一工作令可以通过至少两种 Agent/模型适配器执行，核心治理代码无需修改。
- 同一 Agent 可以切换 Local Worktree 与 Docker Runner，核心任务契约不变。
- DEV 和 QA 的文件系统、凭据和写权限实现有效隔离。
- 不允许 Agent 通过 Shell、浏览器或其他工具绕过 Capability Policy。
- 任务结束后能够清理临时环境和凭据。
- 超时、资源耗尽和外部 Provider 不可用时均有明确状态和恢复策略。

### 阶段 4：Evidence Engine & Conformance Kit

**优先级：P1｜2.0-rc**

目标：把“能执行”升级为“可证明、可复核、可移植”。

交付物：

1. 统一 Evidence Envelope、Manifest 和 Attestation。
2. Evidence Collector、Evidence Store 和 Evidence Verifier。
3. 风险驱动 QA Profile 和验收条件映射。
4. 独立 QA Runner 与平台认证 Artifact 绑定。
5. 协议、后端、Agent、Runner、工具和证据适配器符合性测试。
6. Agent Friendliness Evaluation：项目理解、规范发现、权限遵循、路径约束、QA 独立性和恢复能力测试。
7. 一套可供第三方项目运行的 FPF Conformance CLI。

验收条件：

- 所有正式 QA 结论均绑定固定 SHA、独立主体和可验证 Artifact。
- 证据被篡改、来源缺失、测试命令无效或覆盖不足时，验证器必须拒绝 PASS。
- 每种 Adapter 均有独立符合性测试和能力声明。
- 新 Agent 在无历史对话的情况下，能够通过标准项目任务测试并正确拒绝越权。
- FPF 自身每次修改规范、Schema、Hooks 和治理核心时，自动运行相应回归测试。

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

## 9. 版本与兼容策略

FPF 2.0 必须区分规范版本、Schema 版本、参考实现版本和适配器版本。

| 资产 | 版本策略 | 兼容要求 |
|---|---|---|
| RFC / Protocol | 独立规范版本 | 明确规范性条款和迁移说明 |
| Schema | schema_version | 破坏性变更必须升级主版本 |
| Python Reference Packages | SemVer | 对外 API 变更必须有弃用期 |
| Adapter | adapter_version + capability declaration | 声明支持的协议版本和功能集合 |
| QA Profile | profile_version | 证据集合和语义变更必须可追溯 |
| Conformance Suite | suite_version | 结果绑定测试套件版本和固定 SHA |

兼容性原则：

- 核心契约不得依赖某一 Provider 的私有字段。
- Adapter 必须明确声明支持、部分支持和不支持的能力。
- 不支持的能力不得静默降级。
- 新版本必须提供升级检查和必要的数据迁移。
- Conformance 结果必须绑定 FPF 规范版本、适配器版本和测试套件版本。

---

## 10. FPF 2.0 稳定版验收标准

只有同时满足以下条件，才可以对外声明 FPF 2.0 Stable：

1. 五权治理原则、核心状态机和数据契约形成正式规范。
2. 治理后端、Agent Provider、Runner、Tool Gateway 和 Evidence Store 均有稳定接口。
3. GitHub 参考后端完成授权、任务、Review、Artifact 和生命周期全链路验证。
4. 至少一个可移植隔离 Runner 完成真实执行和恢复验证。
5. DEV 与 QA 在身份、工作区、凭据和权限方面实现可验证隔离。
6. 任务状态只能由可信事实和确定性 Reducer 推进。
7. Evidence Engine 能验证来源、完整性、语义和验收覆盖。
8. Conformance Kit 能独立验证项目、Provider、Runner 和 Adapter。
9. Bootstrap 能在干净的第三方仓库完成初始化和符合性验收。
10. Windows 11 与 Ubuntu 的支持声明均有对应实机验证记录。
11. 文档、Schema、代码和版本兼容矩阵一致。
12. 合并和部署的最终决策权仍由人类保留。

---

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
