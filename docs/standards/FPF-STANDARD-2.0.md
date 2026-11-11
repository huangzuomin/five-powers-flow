# FPF-STANDARD-2.0

## 0. 文档元数据

| 字段 | 值 |
|---|---|
| `standard_id` | `FPF-STANDARD-2.0` |
| `version` | `2.0.0` |
| `status` | `DRAFT` |
| `date` | `2026-11-11` |
| `task_id` | `FPF2-STD-SPEC-01` |
| `base_sha` | `28ebbd5e12da0a0e9a266d736986898fc5731024` |
| `supersedes/derives_from` | `FPF-RFC-001 v1.2.1` |
| `normative_source` | `docs/roadmap/FPF-2.0-STANDARDIZATION-ROADMAP.md` |

本文件是 FPF 2.0 的规范文本草案。它固化路线图中已稳定的契约、边界和验收语义，不把规范要求等同于实现事实、部署事实或独立 QA 结论。

## 1. 范围（Scope）与非目标（Non-goals）

### 1.1 范围

**SCP-01（MUST）** FPF（Five-Powers-Flow）定义面向 AI Agent 原生软件工程的可信治理与执行标准，覆盖权力边界、授权、确定性状态、隔离执行、独立验证和证据链。（源：§1.1）

**SCP-02（MUST）** 本标准化对象包括规范标准、参考运行时、适配器、符合性测试以及发行与运营接口；本文件只固化规范标准部分，不代替其他产品的实现文档。（源：§1.2）

**SCP-03（MUST）** 本标准以模型不确定性受授权、状态机、执行边界、独立验证和证据链约束为基本语义，不以任何模型的智能水平作为可信性依据。（源：§1.1）

**SCP-04（SHOULD）** 实现可按项目选择模型供应商、治理后端、执行后端、测试 Profile、资源预算、项目地图和业务验收规则，但这些选择不得改变第 3 章治理不变项。（源：§1.3）

### 1.2 非目标

**NG-01（MUST NOT）** 本标准不定义替代所有模型供应商的通用 Agent 平台。（源：§1.4）

**NG-02（MUST NOT）** 本标准不定义替代 IDE、Git、CI/CD 或代码托管平台的产品。（源：§1.4）

**NG-03（MUST NOT）** 本标准不把只依赖 Prompt 约束角色行为的多 Agent 聊天框架作为治理机制。（源：§1.4）

**NG-04（MUST NOT）** 本标准不授予系统默认生产权限、自动合并权或自动部署权。（源：§1.4）

**NG-05（MUST NOT）** 本标准不要求 Kubernetes、复杂消息队列或中心化数据库作为运行前提。（源：§1.4）

## 2. 术语与规范性引用

### 2.1 规范性引用

| 引用标识 | 文档 | 用途 |
|---|---|---|
| [RFC2119] | RFC 2119 | 解释规范性关键词的强度 |
| [FPF-RFC-001] | `docs/SPECIFICATION.md`，FPF-RFC-001 v1.2.1 | 五权治理、交接卡、证据与生命周期的派生基线 |
| [ROADMAP] | `docs/roadmap/FPF-2.0-STANDARDIZATION-ROADMAP.md` | 本标准的直接规范来源 |

### 2.2 规范性关键词

**TRM-01（MUST）** 本标准中的英文大写关键词按 [RFC2119] 解释：`MUST`（必须）表示绝对要求；`MUST NOT`（不得）表示绝对禁止；`SHOULD`（应该）表示除非有充分理由，否则应遵守；`SHOULD NOT`（不应该）表示除非有充分理由，否则应避免；`MAY`（可以）表示在不违反更高等级要求时允许选择。（源：§1.3；规范引用：[RFC2119]）

| 术语 | 定义 |
|---|---|
| 权威事实 | 由受信后端、固定版本、真实事件或可核验证据提供的事实，不等同于 Agent 自述。 |
| 可信裁决器 | 依据权威事实、证据和确定性 Reducer 计算状态与门禁结论的中立组件。 |
| 基线 SHA | 工作令或授权绑定的不可歧义代码版本锚点。 |
| Evidence Envelope | 将任务、版本、主体、环境、命令、日志、制品哈希和验证状态绑定在一起的证据信封。 |
| `PLAN_ONLY` | 仅有设计或路线图定义，不表示任何实现、生效或实机验证。 |
| `NOT_RUN` | 指定能力尚未在所需真实环境执行或验证。 |
| `NOT_AUTHORIZED` | 该动作不在本标准或当前工作范围的授权内。 |
| Stable | 仅指第 8 章 ACC-01 至 ACC-13 全部满足后的发行状态；不等同于本文件当前的 `DRAFT` 状态。 |

## 3. 治理不变项

**GOV-01（MUST）** 人类保留最高决策权，Agent 不得取代人类对业务范围、合并、部署及商业和法务事项的最终决定。（源：§1.3）

**GOV-02（MUST NOT）** 代理行政权不得越权修改主干、代签 QA 或擅自部署；未获人类明示授权时，代理不得执行这些动作。（源：§1.3）

**GOV-03（MUST）** 架构规划权与业务开发执行权必须分离；工作令、范围审计和架构裁剪不得被业务执行主体自我替代。（源：§1.3）

**GOV-04（MUST）** 独立监察权必须具有独立身份、独立验证过程以及 DEV 不可修改的证据来源；DEV 与 QA 的签署身份不得重叠。（源：§1.3）

**GOV-05（MUST NOT）** 事实记账权不得替代技术裁决；项目地图、账本或状态投影不得单独产生 QA、合并或部署结论。（源：§1.3）

**GOV-06（MUST）** DEV 交付、QA 通过、人类批准合并和人类批准部署必须保持为不同状态，不得合并为一个“完成”状态。（源：§1.3）

**GOV-07（MUST）** 遇到未授权、未知、证据不足或状态不一致时，默认决策必须是阻断（fail-closed）。（源：§1.3）

**GOV-08（MAY）** 项目可以配置模型供应商、Agent 选择策略、GitHub 或其他符合性后端、Worktree/容器/虚拟机/托管 Runner、测试 Profile、风险等级、资源预算、项目地图、知识库、工具清单和业务验收规则，但不得配置掉 GOV-01 至 GOV-07。（源：§1.3）

## 4. 六平面架构

六平面的正式名称为：`Protocol & Conformance Foundation`、`Governance Plane`、`Control Plane`、`Execution Plane`、`Evidence & Assurance Plane`、`Integration Plane`。`Project Context`、`Observability & Agent Evaluation` 是横向能力，不计入六平面。（源：§3、附录 A.1）

### 4.1 Protocol & Conformance Foundation（协议与符合性基础）

**PLN-01（MUST）** `Protocol & Conformance Foundation` 负责定义角色、主体、权限、动作、拒绝原因，以及任务、授权、交接、QA、证据、合并和发布的数据结构。（源：§3.1）

**PLN-02（MUST）** 该平面负责定义状态机、迁移条件、错误码、事件格式、版本兼容、弃用规则、适配器能力声明和符合性测试要求。（源：§3.1）

**PLN-03（MUST）** 该平面对外提供版本化 RFC、Schema、事件契约、适配器能力声明和 Conformance Kit 接口；契约应能被不同模型、代码托管平台和数据库实现消费。（源：§3.1）

**PLN-04（MUST NOT）** 该平面不得依赖某个模型、代码托管平台或数据库的私有实现，也不得以协议定义替代治理授权或执行动作。（源：§3.1）

### 4.2 Governance Plane（治理平面）

**PLN-05（MUST）** `Governance Plane` 负责登记人类主体和 Agent 主体，绑定五权角色，管理 Scope Grant、授权范围、有效期、撤销、再授权、路径、工具、网络、资源、凭据和操作权限。（源：§3.2）

**PLN-06（MUST）** 该平面必须采用默认拒绝、最小授权和短时有效原则，并把风险等级与人工审批策略纳入治理判定。（源：§3.2）

**PLN-07（MUST）** 该平面对外提供统一的授权、拒绝决策和审计记录契约；提示词中的角色声明不得被当作安全授权。（源：§3.2）

**PLN-08（MUST NOT）** 该平面不得替执行平面运行任务、替 Evidence & Assurance 平面出具 QA 结论，或用账本记录直接代替可信裁决。（源：§3.2）

### 4.3 Control Plane（控制平面）

**PLN-09（MUST）** `Control Plane` 负责规范化任务状态、确定性 Reducer、任务拆分、队列、派发、目标注册、恢复、取消、重试、熔断、事件账本、并发控制和人工交接。（源：§3.3）

**PLN-10（MUST）** 状态决策必须由已验证的规范事实驱动；Agent 自述、Transport completed、文件存在或本地退出码不得单独构成正式 QA PASS 或合并授权。（源：§3.3）

**PLN-11（MUST）** 该平面对外提供 `Request ID`、`Attempt ID`、幂等键、发送回执、状态观测、超时、取消、重试、恢复、事件账本和并发控制语义。（源：§3.3）

**PLN-12（MUST NOT）** 该平面不得新增一套与规范内核脱节的状态机，不得绕过人工审批节点或把观测到的执行状态直接提升为治理结论。（源：§3.3、附录 A.3）

### 4.4 Execution Plane（执行平面）

**PLN-13（MUST）** `Execution Plane` 负责 Agent Session、Runner、Sandbox、Tool Gateway、Credential Broker 及 Resource Budget 的实际执行能力。（源：§3.4）

**PLN-14（MUST）** 该平面必须提供会话创建/恢复/取消/读取、工作区与进程资源分配、文件系统/进程/网络/凭据隔离、工具调用授权入口以及时间、Token、并发、CPU、内存和费用限制。（源：§3.4）

**PLN-15（MUST）** 该平面对外暴露的执行结果必须包含执行主体、Runner、环境、工具调用和结果边界，使上层能够绑定证据和资源预算。（源：§3.4）

**PLN-16（MUST NOT）** 该平面不拥有治理裁决权，不得把模拟结果、未运行结果或本地执行结果单独转化为 QA PASS、合并批准或部署批准。（源：§3.4）

### 4.5 Evidence & Assurance Plane（证据与保证平面）

**PLN-17（MUST）** `Evidence & Assurance Plane` 负责采集原始日志、测试输出和环境信息，独立保存证据制品，记录来源证明，执行结构/哈希/来源/语义/覆盖校验，并承载独立 QA。（源：§3.5）

**PLN-18（MUST）** 该平面必须把独立 QA 与 DEV 分离，并对外生成包含未覆盖风险的 `PASS`、`FAIL`、`BLOCKED`、`INVALID_TEST` 或相应未验证状态报告。（源：§3.5）

**PLN-19（MUST）** 该平面对外契约必须包含 Evidence Envelope、Evidence Store、Provenance、Evidence Verifier 和 Assurance Report 的结构与绑定关系。（源：§3.5、§7.1）

**PLN-20（MUST NOT）** 该平面不得把人类批准合并或发布当作更高等级的 QA 技术证据，也不得用缺少来源、哈希、覆盖或独立性的制品出具 PASS。（源：§3.5、§7.2）

### 4.6 Integration Plane（集成平面）

**PLN-21（MUST）** `Integration Plane` 通过稳定适配器接入 Governance Backend、Model Provider、Agent Adapter、Runner Backend、Tool Adapter 和 Evidence Storage。（源：§3.6）

**PLN-22（MUST）** 适配器必须声明能力、权限、版本和限制，并把外部生态的特定实现与核心协议分离。（源：§3.6）

**PLN-23（MUST）** 该平面对外提供可验证的适配器能力声明、版本兼容声明、权限边界和失败状态；没有真实接口的能力必须能表达 `NOT_SUPPORTED`、`BLOCKED` 或 `NOT_RUN`。（源：§3.6）

**PLN-24（MUST NOT）** 该平面不得以模拟结果伪装成功，不得静默降级未声明的组合，也不得把单一商业模型 Provider 的私有字段写入核心协议。（源：§3.6、§9）

## 5. 核心数据契约与事件模型

以下实体名和字段语义构成 FPF 2.0 的最小规范对象集合。字段名保留协议中的英文标识，便于 Schema、适配器和审计工具互操作。

### 5.1 核心实体契约

| 编号 | 实体 | 必备字段与不变式 |
|---|---|---|
| **CTR-01（MUST）** | `Project Manifest` | 必须包含项目标识、规范版本、治理后端、适配器和策略配置；Manifest 的版本与项目边界必须可被后续门禁读取。（源：§5、§8.7.5） |
| **CTR-02（MUST）** | `Principal / Role Binding` | 必须包含主体标识、主体类型、角色绑定、身份来源、有效期和撤销版本；人类、Agent、服务主体及其角色不得仅由自然语言声明确定。（源：§3.2、§5） |
| **CTR-03（MUST）** | `Capability Profile` | 必须声明可执行动作、路径、工具、网络和资源范围；发现工具不等于获得调用权限。（源：§3.2、§6.2） |
| **CTR-04（MUST）** | `Work Order` | 必须包含任务目标、验收条件、`allowed_paths`、停止条件、项目、基线 SHA、目标分支和重试上限；交付范围不得脱离这些字段被事后解释。（源：§5、§5.2、§8.7.8） |
| **CTR-05（MUST）** | `Scope Grant / Revocation` | 必须绑定工作令内容摘要、基线 SHA、项目、任务、目标分支、授权主体、有效期和重试上限，并用不可变版本或内容摘要表示；撤销必须形成独立可核验事件。（源：§5.2） |
| **CTR-06（MUST）** | `Task Event` | 必须使用统一事件信封，绑定聚合标识、聚合版本、因果链、相关链、主体、来源适配器、外部引用、载荷摘要和回放策略；历史事件追加写入，不以新状态覆盖。（源：§5.1） |
| **CTR-07（MUST）** | `Dispatch Request / Receipt` | 必须包含派发意图、目标、`request_id`、`attempt_id`、幂等键和回执；回执只证明对应派发动作的观察结果，不自动证明远端完成或未执行。（源：§3.3、§5、§4.1） |
| **CTR-08（MUST）** | `Execution Envelope` | 必须记录 Agent、Runner、环境、工具调用、开始/结束时间、资源边界和执行结果；执行信封不授予治理裁决权。（源：§3.4、§5） |
| **CTR-09（MUST）** | `DEV Handoff` | 必须包含交付任务、代码 SHA、自测结果、未验证项和证据引用；DEV 自测不得替代独立 QA。（源：§5、§7.4、[FPF-RFC-001]） |
| **CTR-10（MUST）** | `QA Result` | 必须包含独立验收主体、固定 `tested_sha`、结论、下一动作和证据引用；结论必须绑定被测版本，DEV 与 QA 签署身份不得重叠。（源：§5、§7.2、[FPF-RFC-001]） |
| **CTR-11（MUST）** | `Evidence Manifest / Attestation` | 必须列出证据来源、类型、适用 Profile、验收覆盖、采集器、哈希和验证声明；缺失或不一致时不能形成有效保证。（源：§5、§7.1、§7.4） |
| **CTR-12（MUST）** | `Merge / Release Record` | 必须记录人类批准主体、批准时间、合并版本或发布版本及对应事实引用；Agent 自述不得生成合并或发布记录。（源：§1.3、§5、§10） |
| **CTR-13（MUST）** | `Context Pack` | 必须绑定项目版本、来源和更新时间，并包含任务执行所需的规范、架构、知识和历史决策快照；Context 不得成为高于授权和事实记录的第二权威账本。（源：§3.7、§5） |

### 5.2 统一事件信封与事件名

**EVT-01（MUST）** 每个事件信封必须包含 `event_id`、`event_schema_version`、`aggregate_id`、`aggregate_version`、`causation_id`、`correlation_id`、`recorded_at`、`occurred_at`、`sequence`、`topic`、`actor`、`source_adapter`、`object_refs`、`payload_digest` 和 `replay_policy`。（源：§5.1）

**EVT-02（MUST）** `event_id` 采用 UUIDv7 以获得局部时间排序特征，但不得把 UUIDv7 解释为全局严格单调顺序；全局逻辑顺序由权威存储分配的 `sequence` 保证。（源：§5.1）

**EVT-03（MUST）** `aggregate_version` 必须为单调递增整型并用于原子 CAS；`recorded_at` 使用权威存储确认落盘的 UTC 时间，`occurred_at` 表示适配器或客户端观察到的 UTC 时间。（源：§5.1）

**EVT-04（MUST）** `actor` 必须区分 `HUMAN_OPERATOR`、`DEV_AGENT` 和 `QA_AGENT`；`object_refs` 至少能引用 Commit SHA、PR Number、Workflow Run ID 或 Artifact SHA 中适用的权威对象。（源：§5.1）

**EVT-05（MUST）** 标准事件名必须覆盖 `fpf.lifecycle.dispatched`、`DEV_SUBMITTED`、`QA_VERIFIED`、`QA_FAILED`、`REVOKED`、`UNBLOCKED`、`HUMAN_RESOLVED`、`HUMAN_ABORT`、`POLICY_WAIVER`、`SCOPE_AMEND`、`ROLLBACK_WORK_ORDER`、`CANCEL_REQUESTED`、`CANCEL_PENDING`、`REMOTE_CANCELLED`、`REMOTE_SUCCEEDED` 和 `CANCEL_CONFLICT` 所表达的生命周期、治理、范围和回滚语义。（源：§5.1、§7.2、§8.7）

**EVT-06（MUST）** 聚合更新、确定性 `sequence` 分配、不可变事件写入和 Transactional Outbox 写入必须位于同一事务；CAS 影响行数不为 1 时必须回滚并转入并发冲突/对账路径。（源：§5.1）

**EVT-07（MUST）** Outbox 与 Inbox 必须物理和逻辑分权；Outbox 只确认 Dispatcher 投递，消费端必须以 `(consumer_name, event_id)` 唯一约束在本地事务中实现幂等投影，并支持 At-Least-Once 投递语义。（源：§5.1）

**EVT-08（MUST）** `replay_policy` 默认必须为 `PROJECTION_ONLY`；事件回放只能重建投影或审查，运行时必须替换或禁用 Tool Gateway、网络客户端和 Agent Provider，禁止外部网络请求、写操作或模型调用。（源：§5.1）

**EVT-09（MUST）** 命令重执行必须生成全新的 `request_id` 和递增的 `attempt_id`，重新经过五权授权、参数校验和幂等派发；不得借历史事件回放隐式重发外部请求。（源：§5.1、§5.2）

**EVT-10（MUST）** 授权版本、工作令内容、基线、权限或范围发生变化，或权限被撤销时，必须产生可核验的版本/撤销事件并触发阻断或重新授权；事件流只能追加写入，状态只能由经过验证的事件流确定性归约。（源：§5.2）

## 6. 证据与保证

### 6.1 Evidence Envelope 与证据等级

**EVD-01（MUST）** 每项证据必须绑定 `task_id`、`request_id`、`attempt_id`、`tested_sha`、`baseline_sha`、执行主体及身份来源、Runner 身份、环境摘要、工具链版本、实际命令、起止时间和退出码。（源：§7.1）

**EVD-02（MUST）** 证据必须引用原始日志和制品，记录 Artifact SHA-256、证据类型、适用 Profile、覆盖的验收条件、来源证明、采集器版本和验证状态。（源：§7.1）

**EVD-03（MUST）** Evidence Verifier 必须分别核验 Provenance（来源可信度）、Reproducibility（可复现性）、Isolation（执行隔离度）、Independence（主体独立性）和 Coverage（验收覆盖率）五个维度；任一维度不得替代其他维度。（源：§7.2）

**EVD-04（MUST）** 历史执行记录标签必须按技术可信度区分：T0 为无结构化证据的 Agent 自述且可信度为零；T1 为本地观察与日志；T2 为固定环境的确定性测试输出；T3 为隔离 Runner 生成且带物理 SHA-256 的制品包。标签只表示执行手段，不表示治理状态。（源：§7.2）

**EVD-05（MUST NOT）** 人类批准合并或发布不得被归入 QA 证据可信等级；它们是治理生命周期状态跃迁，不能补足独立测试凭据。（源：§7.2）

### 6.2 Profile、可信裁决器与 fail-closed

**EVD-06（MUST）** Docs Profile 至少要求 Markdown 语法、外部链接和 `allowed_paths` 全部满足；Library Profile 至少要求单元测试、验收断言和禁止路径修改全部满足；Core Profile 至少要求全量回归、核心分支覆盖和物理哈希对齐全部满足；Release Profile 至少要求全量套件与 E2E、跨平台矩阵和干净工作树全部满足，并执行 DEV、独立 QA、人类发布授权人三主体分离。（源：§7.2）

**EVD-07（MUST）** 可信裁决器必须验证证据结构、哈希、来源、语义和验收覆盖，核对固定 SHA 与工作令，输出 `PASS`、`FAIL`、`BLOCKED`、`INVALID_TEST` 或未覆盖风险；不得以 Agent 自述替代裁决。（源：§3.3、§3.5、§7.2、§7.4）

**EVD-08（MUST）** 证据缺失、未知、过期、不一致、无法证明来源或无法证明覆盖时，验证器必须 fail-closed；不得因文件存在、哈希一致、空命令、预置截图或无意义输出而判定通过。（源：§1.3、§7.4）

**EVD-09（MUST）** 生命周期状态必须由确定性事件驱动，不能由自由文本跳跃；正式状态至少区分 `REVOKED`、`INVALID_TEST`、`BLOCKED`、`QA_FAILED`、`QA_VERIFIED`、`HUMAN_APPROVED`、`HUMAN_REJECTED`、`MERGED`、`HUMAN_RESOLUTION_REQUIRED` 及回滚状态。（源：§7.2）

**EVD-10（MUST）** `INVALID_TEST` 的环境重试预算与 DEV 业务返工次数必须分离，默认环境重试上限为 2 次；预算耗尽必须进入 `HUMAN_RESOLUTION_REQUIRED`。（源：§7.2）

**EVD-11（MUST）** `BLOCKED` 只能在根本原因经权威事实消除且 Reducer 生成 `UNBLOCKED` 后恢复；`REVOKED` 覆盖所有终态前的活动状态，已合入或已发布的任务不得直接倒退为 `REVOKED`，必须走回滚治理通道。（源：§7.2）

**EVD-12（MUST NOT）** 远端取消未收到权威确认时，不得把任务直接标记为已取消或盲目重发；取消与完成竞争时必须保留并核验已生成制品，按 `CANCEL_CONFLICT` 进入对账。（源：§7.2）

**EVD-13（MUST）** 测试证据的语义必须匹配验收条件：API 证据绑定真实请求/响应，数据库证据绑定真实连接/事务/持久化检查，浏览器证据绑定真实页面/DOM 断言，Artifact 绑定工作流、Runner、固定 SHA 和独立审查主体。（源：§7.4）

## 7. 三产品与六维兼容

### 7.1 三产品

**PRD-01（MUST）** `FPF Standard` 是五权治理标准库，包含规范文档、JSON Schemas、核心事件契约和规范元模型，并中立定义产品边界、权限模型和数据契约。（源：§9）

**PRD-02（MUST）** `FPF Reference Runtime` 是参考执行运行时，包含 Core Kernel、Control Plane、三层 Runner，并作为遵循 Standard 的官方参考实现边界；本条不构成实现完成声明。（源：§9）

**PRD-03（MUST）** `FPF Conformance` 是符合性验证套件，包含零依赖基础规范校验器、权威官方测试向量、绑定 Standard 哈希的 Conformance CLI 和双向独立验证。（源：§9）

**PRD-04（MUST）** Conformance 必须同时验证 Standard 规范自洽性和 Runtime 实现合规性，并以独立信任根、双实现交叉验证、带外公钥锚定和可复现构建消除循环信任。（源：§9）

**PRD-05（MUST）** `Agent Evaluation Framework` 作为附属评测包，必须与 Conformance 的确定性规范/实现验证分轨，独立评估 Agent 行为稳定性与可靠度，不得替代 Conformance 结论。（源：§9、§10）

### 7.2 六维版本兼容矩阵

**CMP-01（MUST）** 兼容矩阵必须包含六个维度：`Standard`、`Schema`、`Runtime`、`Adapter`、`Conformance` 和 `Agent Eval Dataset`。（源：§9、§10）

**CMP-02（MUST）** Reference Runtime 与 Adapter 必须在 Manifest 中显式声明支持的规范版本、Schema 版本和能力集；声明至少能表达 `supported_standard_versions`、`declared_capabilities` 和 `schema_version`。（源：§9）

**CMP-03（MUST）** 兼容性声明必须以 Conformance Suite 在 CI 中实际通过的组合为准；Manifest 单独声明不得形成兼容结论。（源：§9）

**CMP-04（MUST）** “Runtime 2.1 支持 Standard 2.0”只表示 Runtime 2.1 能按 Conformance 实测向下兼容执行 Standard 2.0，不表示所有未测试组合自动兼容。（源：§9）

**CMP-05（MUST NOT）** 初始化时发现六维组合未声明或不兼容，必须以 `INCOMPATIBLE_VERSION_COMBINATION` 拒绝加载，不得静默空转或隐式降级。（源：§9）

**CMP-06（MUST）** 草案标识与正式发行版本必须分开；`2.0.x-draft`、`draft-2026-10-31` 和 `v2.0-draft` 只能标识开发草案，不得用于生产合规认证。（源：§9）

**CMP-07（MUST）** 正式 `2.0.0` 组合必须以 `v2.0` Schema、`2.0.0` 或更高的实测 Runtime、`v2.0` Adapter 能力集、绑定 2.0.0 信任根的 `v2.0.0` Conformance 和独立版本 `eval-2026.10` 为兼容基线；`2.0.x` 补丁版本保持向下兼容规则。（源：§9）

**CMP-08（MUST NOT）** 核心协议不得引入单一商业模型 Provider 的私有字段或非标准调用；能力声明、适配器限制和版本组合必须保持可替换。（源：§9）

## 8. 稳定版验收标准

FPF 2.0 Stable 的判定对象是 ACC-01 至 ACC-13 的联合结果；本文件当前状态仍为 `DRAFT`。

**ACC-01（MUST）** 五权治理原则、核心状态机、事件因果模型（包括 UUIDv7 局部时间排序、`sequence` 严格单调递增、原生条件更新原子 CAS、Transactional Outbox 和 `PROJECTION_ONLY` 零副作用回放）及数据契约形成正式规范。判定方式：逐项检查版本化规范、Schema、事件契约和回放隔离测试记录。（源：§10 第 1 条）

**ACC-02（MUST）** Governance Backend、Agent Provider、Runner、Tool Gateway 和 Evidence Store 均具有稳定接口与确定性契约测试。判定方式：每个接口均有固定输入、输出、错误码和可重复的契约测试结果，缺一项即不通过。（源：§10 第 2 条）

**ACC-03（MUST）** GitHub 参考后端完成授权、任务、严格绑定 Commit SHA 的 Review、Artifact 和生命周期全链路验证。判定方式：以固定 SHA 的真实链路记录核对上述五类对象及其关联关系。（源：§10 第 3 条）

**ACC-04（MUST）** 对账与恢复协议完成 Provider Class A/B/C 分级、显式幂等作用域、并发去重、60 秒带抖动探针退避、`NOT_FOUND ≠ PROVEN_NOT_EXECUTED` 延迟窗口、禁止崩溃盲目重发和 `REMOTE_RUNNING` 两层远端子状态验证。判定方式：对每类 Provider、未知结果、并发重复和恢复场景执行确定性测试，逐项保留结果。（源：§10 第 4 条）

**ACC-05（MUST）** Local Worktree（Windows 11 原生生产级一级支持）与 Docker Sandbox 完成生产级实机执行和崩溃恢复验证。判定方式：分别提供真实环境、固定版本、崩溃注入、恢复结果和物理证据，模拟测试不计入。（源：§10 第 5 条）

**ACC-06（MUST）** Windows 11 原生环境落实 DEV/QA 独立账户、源码只读 ACL、Credential Broker 命名管道 ACL 与短期令牌代理、`CREATE_SUSPENDED` 绑定防逃逸及本地防火墙默认拒绝出站规则。判定方式：逐项执行身份、ACL、Broker、进程逃逸和网络旁路测试并核对实机结果。（源：§10 第 6 条）

**ACC-07（MUST）** 任务状态只能由可信事实和确定性 Reducer 推进，并完整支持全局 `REVOKED`、`HUMAN_RESOLUTION_REQUIRED`、`INVALID_TEST` 独立重试预算、带制品/计数的 `QA_FAILED`、`HUMAN_REJECTED` 归档分支及 `ROLLBACK` 异常跃迁。判定方式：对正常、非法跳跃、撤销、环境故障、否决和回滚事件执行状态机测试。（源：§10 第 7 条）

**ACC-08（MUST）** Evidence Engine 依据五维证据模型和 Profile 量化门槛验证来源、完整性和验收覆盖，达到 100% 测试成功率、100% 验收覆盖率，并执行 Release Profile 三主体防兼任。判定方式：用缺失来源、错误 SHA、覆盖缺口和主体兼任反例确认门禁均拒绝。（源：§10 第 8 条）

**ACC-09（MUST）** FPF Conformance Suite 具备基于 Declared Capabilities 的确定性硬门禁、零依赖基础校验器和黄金测试向量信任根，并与概率性 Agent Evaluation 分轨独立出具报告。判定方式：对能力声明、标准元模型、黄金向量、双校验器和评测报告分别核验独立产物。（源：§10 第 9 条）

**ACC-10（MUST）** Bootstrap 能在干净第三方仓库完成初始化，并通过 Doctor 和 Conformance 验收。判定方式：使用未预置 FPF 文件的第三方仓库，记录初始化、Doctor、Conformance 的固定输出和失败边界。（源：§10 第 10 条）

**ACC-11（MUST）** Windows 11 与 Ubuntu 跨平台兼容矩阵具有对应实机测试记录，覆盖路径规范、进程树回收、权限映射和防火墙规则。判定方式：逐个平台、执行后端和维度核对真实运行记录，不以远端模拟替代。（源：§10 第 11 条）

**ACC-12（MUST）** FPF Standard、Reference Runtime、Conformance 三大产品的双向验证体系，以及 Standard × Schema × Runtime × Adapter × Conformance × Eval Dataset 六维版本兼容矩阵，必须清晰且一致。判定方式：核对产品间验证方向、信任根、Manifest 声明、实测组合和不兼容拒绝记录。（源：§10 第 12 条）

**ACC-13（MUST）** 合并和部署的最终决策权始终由人类保留，并且不存在凭据泄露或自动化旁路。判定方式：检查权限配置、主体分离、凭据存储、旁路对抗测试和人类批准记录；任一旁路或泄露即不通过。（源：§10 第 13 条）

## 9. 一致性要求总表

下表汇总第 3 至第 8 章全部带编号条款；每一行对应一个唯一条款 ID、规范等级和路线图具体章节。

| 条款 | 等级 | 路线图章节 |
|---|---|---|
| GOV-01 | MUST | §1.3 |
| GOV-02 | MUST NOT | §1.3 |
| GOV-03 | MUST | §1.3 |
| GOV-04 | MUST | §1.3 |
| GOV-05 | MUST NOT | §1.3 |
| GOV-06 | MUST | §1.3 |
| GOV-07 | MUST | §1.3 |
| GOV-08 | MAY | §1.3 |
| PLN-01 | MUST | §3.1 |
| PLN-02 | MUST | §3.1 |
| PLN-03 | MUST | §3.1 |
| PLN-04 | MUST NOT | §3.1 |
| PLN-05 | MUST | §3.2 |
| PLN-06 | MUST | §3.2 |
| PLN-07 | MUST | §3.2 |
| PLN-08 | MUST NOT | §3.2 |
| PLN-09 | MUST | §3.3 |
| PLN-10 | MUST | §3.3 |
| PLN-11 | MUST | §3.3 |
| PLN-12 | MUST NOT | §3.3、附录 A.3 |
| PLN-13 | MUST | §3.4 |
| PLN-14 | MUST | §3.4 |
| PLN-15 | MUST | §3.4 |
| PLN-16 | MUST NOT | §3.4 |
| PLN-17 | MUST | §3.5 |
| PLN-18 | MUST | §3.5 |
| PLN-19 | MUST | §3.5、§7.1 |
| PLN-20 | MUST NOT | §3.5、§7.2 |
| PLN-21 | MUST | §3.6 |
| PLN-22 | MUST | §3.6 |
| PLN-23 | MUST | §3.6 |
| PLN-24 | MUST NOT | §3.6、§9 |
| CTR-01 | MUST | §5、§8.7.5 |
| CTR-02 | MUST | §3.2、§5 |
| CTR-03 | MUST | §3.2、§6.2 |
| CTR-04 | MUST | §5、§5.2、§8.7.8 |
| CTR-05 | MUST | §5.2 |
| CTR-06 | MUST | §5.1 |
| CTR-07 | MUST | §3.3、§5、§4.1 |
| CTR-08 | MUST | §3.4、§5 |
| CTR-09 | MUST | §5、§7.4、FPF-RFC-001 §4.1 |
| CTR-10 | MUST | §5、§7.2、FPF-RFC-001 §4.2 |
| CTR-11 | MUST | §5、§7.1、§7.4 |
| CTR-12 | MUST | §1.3、§5、§10 |
| CTR-13 | MUST | §3.7、§5 |
| EVT-01 | MUST | §5.1 |
| EVT-02 | MUST | §5.1 |
| EVT-03 | MUST | §5.1 |
| EVT-04 | MUST | §5.1 |
| EVT-05 | MUST | §5.1、§7.2、§8.7 |
| EVT-06 | MUST | §5.1 |
| EVT-07 | MUST | §5.1 |
| EVT-08 | MUST | §5.1 |
| EVT-09 | MUST | §5.1、§5.2 |
| EVT-10 | MUST | §5.2 |
| EVD-01 | MUST | §7.1 |
| EVD-02 | MUST | §7.1 |
| EVD-03 | MUST | §7.2 |
| EVD-04 | MUST | §7.2 |
| EVD-05 | MUST NOT | §7.2 |
| EVD-06 | MUST | §7.2 |
| EVD-07 | MUST | §3.3、§3.5、§7.2、§7.4 |
| EVD-08 | MUST | §1.3、§7.4 |
| EVD-09 | MUST | §7.2 |
| EVD-10 | MUST | §7.2 |
| EVD-11 | MUST | §7.2 |
| EVD-12 | MUST NOT | §7.2 |
| EVD-13 | MUST | §7.4 |
| PRD-01 | MUST | §9 |
| PRD-02 | MUST | §9 |
| PRD-03 | MUST | §9 |
| PRD-04 | MUST | §9 |
| PRD-05 | MUST | §9、§10 |
| CMP-01 | MUST | §9、§10 |
| CMP-02 | MUST | §9 |
| CMP-03 | MUST | §9 |
| CMP-04 | MUST | §9 |
| CMP-05 | MUST NOT | §9 |
| CMP-06 | MUST | §9 |
| CMP-07 | MUST | §9 |
| CMP-08 | MUST NOT | §9 |
| ACC-01 | MUST | §10 第 1 条 |
| ACC-02 | MUST | §10 第 2 条 |
| ACC-03 | MUST | §10 第 3 条 |
| ACC-04 | MUST | §10 第 4 条 |
| ACC-05 | MUST | §10 第 5 条 |
| ACC-06 | MUST | §10 第 6 条 |
| ACC-07 | MUST | §10 第 7 条 |
| ACC-08 | MUST | §10 第 8 条 |
| ACC-09 | MUST | §10 第 9 条 |
| ACC-10 | MUST | §10 第 10 条 |
| ACC-11 | MUST | §10 第 11 条 |
| ACC-12 | MUST | §10 第 12 条 |
| ACC-13 | MUST | §10 第 13 条 |

## 10. 版本与变更控制

**VER-01（MUST）** 正式发行版本采用 `MAJOR.MINOR.PATCH` 形式；Standard、Schema、Runtime、Adapter、Conformance 和 Agent Eval Dataset 的版本必须分别声明，不得用草案 ID 代替正式版本。（源：§9）

**VER-02（MUST）** 破坏五权核心契约、数据语义、事件不变式或兼容承诺的变更必须提升 MAJOR；保持既有语义并增加向后兼容能力的变更使用 MINOR；不改变规范语义的勘误和澄清使用 PATCH。（源：§9、§10）

**VER-03（MUST）** 每个 Runtime 和 Adapter 必须在 Manifest 显式声明支持的 Standard、Schema 和能力集，并以 Conformance 实测结果锁定兼容组合。（源：§9）

**VER-04（MUST）** 草案版本必须标注 `draft` 或等价状态，禁止将草案组合用于生产合规认证；正式版本的兼容声明必须区分“声明”与“已实测通过”。（源：§9）

**VER-05（MUST）** 废弃流程必须发布废弃说明、受影响版本、替代契约、兼容窗口和迁移验证；在窗口内仍需按既有版本规则处理，窗口结束后才可移除，并同步更新 Conformance 测试向量和兼容矩阵。（源：§3.1、§9）

**VER-06（MUST）** 本标准由 `FPF-RFC-001 v1.2.1` 派生，不复制其正文；五权边界、DEV/QA/合并/部署状态分离、独立证据和人类最终批准语义保持兼容。发现语义冲突时必须标记待裁决，不得静默覆盖 RFC 或路线图。（源：§1.2、§1.3、§9；关联：[FPF-RFC-001]）

**VER-07（MUST）** 从 RFC-001 迁移到 Standard 2.0 时，迁移工具或人工记录必须绑定源版本、目标版本、基线 SHA、契约映射和未迁移项；迁移后的状态与证据不得把 DEV 交付提升为 QA 或人类批准。（源：§5、§7、§9；关联：[FPF-RFC-001]）

**VER-08（MUST NOT）** 在本文件 `status: DRAFT` 或 ACC-01 至 ACC-13 未全部有可测证据时，不得对外宣称 FPF 2.0 Stable、实现完成、部署完成或生产就绪。（源：§2、§10）

## 11. 未实施声明

本章是状态边界声明，不把路线图设计要求改写为实现事实。

| 编号 | 项目 | 状态与边界 |
|---|---|---|
| **NIM-01（MUST）** | G2 宪制强制力落地 | `PLAN_ONLY`；平台/密码学级强制、独立批准和签名门禁不因本标准文本而生效。（源：§8.7.2） |
| **NIM-02（MUST）** | G3 凭据与身份边界 | `PLAN_ONLY`；静态密钥零落盘、轮换、吊销和 OS/CI 凭据边界不因本标准文本而生效。（源：§8.7.3） |
| **NIM-03（MUST）** | G4 状态机归约接入 | `PLAN_ONLY`；GitHub 事件源到 Reducer/投影的自动接入不因本标准文本而生效。（源：§8.7.4） |
| **NIM-04（MUST）** | H1 项目注册与控制面隔离 | `PLAN_ONLY`；项目注册表、控制面路径白名单和 Manifest 校验不因本标准文本而生效。（源：§8.7.5） |
| **NIM-05（MUST）** | H2 worktree 生命周期 | `PLAN_ONLY`；标记、TTL、三条件回收和回收审计不因本标准文本而生效。（源：§8.7.6） |
| **NIM-06（MUST）** | H3 部署就绪门禁 | `PLAN_ONLY`；预发 smoke、迁移版本断言和关键表断言不因本标准文本而生效。（源：§8.7.7） |
| **NIM-07（MUST）** | H4 范围修正协议 | `PLAN_ONLY`；`SCOPE_AMEND` 的事前范围校验不因本标准文本而生效。（源：§8.7.8） |

**NIM-08（MUST NOT）** 生产部署与真实计费调用均为 `NOT_AUTHORIZED`，本标准不授予任何部署、生产数据访问或真实计费权限。（源：§2.5、§8.7.7、§11）

**NIM-09（MUST）** 路线图标记为 `NOT_RUN` 的真实外部 Provider 长会话、Windows WFP 内核驱动、跨平台本地实机交叉运行及其他未验证能力，必须继续标记为 `NOT_RUN`，直到出现固定版本、真实环境和可复核证据。（源：§2.5、附录 A.2）

**NIM-10（MUST）** 本文件是规范文本，不构成任何代码、运行时、Conformance、部署或生产能力的实现完成声明；文档验收也不等于实现验收、独立 QA 通过、合并授权或部署授权。（源：§2、§10、附录 A）
