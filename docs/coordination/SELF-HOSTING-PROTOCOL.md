# FPF 自举研发协议

本协议是 FPF 自举研发的版本治理规则。它在通过独立 QA、`POLICY_CHANGE` / `GATE_PR` 门禁并由人类合并后才对主干生效；在此之前不得把本文件当作已经改变主干权限的事实。本协议只建立制度和最小路径保护，不实现 L1、L2 或 L3 的 Runtime autonomy，不把规划、Mock 测试、离线演练或单元测试称为真实自举运行能力。

本协议只有以下十个核心章节。FPF-RFC-001、`docs/SPECIFICATION.md`、当前有效的状态机、仓库服务端保护规则以及人类明确授权的优先级高于本协议；本协议不得削弱这些上位约束。

## 1. 目的、适用范围、术语和规范优先级

### 1.1 目的与范围

本协议约束稳定版本组织下一候选版本的研发、验证、合并、晋升、观察和恢复。适用对象是 Controller N 对 Candidate N+1 的自举研发，不是普通功能开发流程的替代物，也不是新增的治理权力或新的任务状态机。

Issue #77 的本轮原子变更仅允许三条路径：

- `docs/coordination/SELF-HOSTING-PROTOCOL.md`；
- `packages/fpf_policy/protected.py`；
- `tests/test_self_hosting_policy.py`。

任何超出这三条路径的变更都不属于本协议任务。`docs/coordination/project-map.md`、`docs/SPECIFICATION.md`、`schemas/`、`.github/`、`.fpf/`、`packages/fpf_coordinator/`、`packages/fpf_runtime/`、`packages/fpf_gates/`、`README.md` 和 `CHANGELOG.md` 等路径不得因本协议而被修改。

### 1.2 术语

- **Controller N**：当前稳定控制版本。它由一个明确的、完整的 Git 不可变 commit SHA 锚定，而不是由会移动的分支名或工作目录代表。
- **Candidate N+1**：从 Controller N 的固定 SHA 派生的候选版本，必须在独立 branch、独立 Worktree 和独立 execution environment 中研发。
- **固定 SHA**：提交对象的完整 SHA-1 标识；`tested_code_sha`、`baseline_sha` 和 QA 测试对象必须按任务卡和实际 Git 对象核对，不能用短 SHA、标签或当前分支头替代。
- **独立 QA**：与 DEV 身份、工作区、可写凭据和测试代码来源相分离的审查主体。DEV 自测不是独立 QA。
- **真实证据（real evidence）**：由实际执行产生、可重算并绑定被测 SHA 的日志、退出码、测试结果、证据清单和物理哈希；聊天声明或 Mock 输出不构成真实证据。
- **`NOT_RUN`**：某项检查没有真实执行，必须保留为未执行边界，不得转写为 PASS、已覆盖或“无风险”。
- **`SCOPE_GRANT`、`QA_ADMISSION`、`DEV_HANDOFF`、`QA_RESULT`**：分别表示人类范围授权、开发前独立准入、DEV 提测交接和独立 QA 裁决。每张卡的身份、范围、SHA、时序和证据都必须可追溯。

### 1.3 规范优先级与非目标

本协议继承 FPF-RFC-001 的五权分立、三道人类主权门和现有 24 阶段状态机；自举生命周期只能叠加版本和信任边界，不能替换状态机。AEC A—G 已记录的交付事实也不等于 Provider、持续派发、跨进程隔离、自动晋升或恢复已经实现。

本任务不实现真实 Provider 派发、ChatGPT 浏览器交互、Codex Thread Bridge、Daemon 调度闭环、Feature/Slice Ticket 运行时代码、跨进程凭据撤销、自动 Worktree 管理、自动晋升或自动回滚；这些边界必须在成熟度声明中保持 `NOT_RUN`。

## 2. Controller N / Candidate N+1 双版本模型与信任根

### 2.1 Controller N 的不可变锚点

Controller N 必须记录 `controller_sha`，并固定到一个可由 Git 验证为 `commit` 对象的完整不可变 commit SHA。Controller N 的源码、治理脚本、执行环境和独立 QA 工具版本都以该 SHA 或经人类认可的可信信任根为准；不能用“当前 main”“最新版本”或 Candidate 自己生成的标签替代。

Controller N 在 Candidate 工作期间保持只读稳定：不得由 Candidate 改写、重写历史、替换、删除、移动或热更新。所有输入、授权、任务包、收据和证据都应记录其对应的 Controller SHA；若 SHA 无法解析、对象类型不是 `commit`、或基线发生漂移，立即熔断并标记 `BLOCKED`。

### 2.2 Candidate N+1 的隔离

Candidate N+1 必须从固定的 Controller SHA 创建独立 branch、独立 Git Worktree 和独立 execution environment。Candidate 的工作目录、进程、用户边界、环境变量、缓存、写入权限和可用凭据都不得与 Controller N 的控制工位共享可写状态；QA 还必须从可信基线检出只读或独立测试 Worktree，不能测试 DEV 工位的脏状态。

Candidate 只能产出候选代码、测试和证据，并通过受控的交接卡和 PR 交换信息。Candidate 不得自行修改授权，不得控制、修改、替换或批准 Controller N，也不得取得 Controller 的管理凭据或信任根。Candidate 不得自选自己成为下一任 Controller，不得把自己的测试、声明或批准当成独立授权。

### 2.3 原地更新和激活边界

禁止原地自更新：Candidate 不能在 Controller N 正在运行的工作目录、进程、分支、部署环境或控制数据库中覆盖自身或 Controller。`MERGED` 不等于 `ACTIVATED`；代码合入后仍须由人类授权在独立环境完成启动、兼容性和观察验证，才可声明 Candidate N+1 激活。

信任根包括 Controller 固定 SHA、独立 QA 执行器、仓库服务端分支保护、CODEOWNERS、Secrets、Runner trust root 和人类审批身份。Candidate 无权改变其中任何一项；其中的管理权只能由相应的人类负责人按既有治理流程行使。

## 3. 自举研发生命周期：目标输入、设计、授权、Admission、DEV、独立 QA、人工合并、晋升、观察、回滚

### 3.1 固定顺序

一次 Candidate 生命周期必须按以下顺序执行，任何失败或未知状态都不得自动跳过阶段：

1. **目标输入**：人类提出目标和目标环境，Controller 记录来源；Agent 不得自行发明扩大目标。
2. **设计与范围**：DEV 形成最小设计、风险分级和 `WORK_ORDER`，列出 `baseline_sha`、`allowed_paths`、`forbidden_paths`、`allowed_actions`、预算和有效期。
3. **人类范围授权**：人类签发或明确确认 `SCOPE_GRANT`。这是本协议 Candidate 生命周期的第一个、不可代理的人类主权闸门；未授权时不能创建 Candidate 或开始编码。
4. **独立 QA Admission**：QA 在 DEV 编码前，依据固定 Controller SHA、真实工作令和隔离方案独立签发 `QA_ADMISSION`。QA 与 DEV 身份、工作区和可写代码相分离。
5. **受限 DEV**：Candidate 只能在授权的 branch、Worktree、execution environment 和路径中执行 A1—A7；DEV 交付 `DEV_HANDOFF` 时必须绑定真实候选 commit SHA。
6. **固定 SHA 独立 QA**：QA 从可信环境检出该确切 SHA，核验完整 Git diff、身份分离、风险、测试、证据和 `NOT_RUN` 清单，并签署绑定 `tested_sha` 的 `QA_RESULT`。不能以 DEV 自测或 Mock 替代。
7. **政策门禁与第二审查**：本协议、`protected.py` 或测试等受保护/治理变更必须使用 `POLICY_CHANGE`；触及受保护路径或 `tests/` 时必须由生产 `classify` 路由为 `GATE_PR`。`GATE_PR` 的独立 QA、真实 QA Artifact、第二名独立审查者和固定 SHA 条件不可由 Candidate 自行豁免。
8. **人类代码合并与晋升决定**：在独立 QA PASS、符合性核验、固定 SHA 一致、第二名独立审查和物理证据齐全后，由人类批准代码合并并决定是否晋升，再由人类执行代码合并。这是本协议 Candidate 生命周期的第二个、不可代理的人类主权闸门；Agent 只能提出建议，不能代签或自动合并。
9. **独立环境激活和观察**：合并不自动激活。人类授权后在独立环境启动 Candidate，观察兼容性、错误、权限和回滚信号；任一证据缺失则保持 `NOT_RUN` 或 `BLOCKED`。
10. **事实记账与恢复**：代码合并事实由 Scribe 按独立 QA 证据另行提出 `MAP_UPDATE`，并经过现行地图人类闸门；失败时回到已知良好 Controller，而不是由 Candidate 自行恢复主权。

本协议的两个、不可代理的人类主权闸门是范围授权闸门和代码合并/晋升闸门。它们不取消 FPF 全局既有的项目地图合并闸门；Scribe、DEV、QA 和 Coordinator 都不得合并或代替人类执行该闸门。

### 3.2 A1—A7 授权动作边界

`SCOPE_GRANT` 对 A1—A7 的授权只能逐项限定，授权记录至少要能追溯 authorizer、授权时间、失效时间、固定基线、目标环境、`allowed_paths`、`forbidden_paths`、`allowed_actions` 和预算。记录的存在不代表已经执行；每项执行都要有真实收据，未执行项标为 `NOT_RUN`。

| 动作 | 允许的最小边界 | 明确禁止 |
| --- | --- | --- |
| `A1_CREATE_CANDIDATE_BRANCH` | 从固定 Controller SHA 创建候选 branch | 改写或直接写入 Controller/main、强推覆盖稳定历史 |
| `A2_CREATE_ISOLATED_WORKTREE` | 创建与 Controller、QA 隔离的独立 Worktree | 复用 Controller 可写目录、共享控制凭据或隐藏状态 |
| `A3_RESTRICTED_EDIT_ALLOWED_PATHS` | 仅编辑工作令列出的 `allowed_paths` | 扩大路径、编辑 `forbidden_paths`、修改分支保护或治理信任根 |
| `A4_EXECUTE_LOCAL_TESTS` | 在 Candidate 环境运行已列出的本地检查并保留退出码 | 把本地自测冒充独立 QA、删改失败日志或伪造 PASS |
| `A5_CREATE_DEV_COMMIT` | 形成可审计的候选 commit 和 `DEV_HANDOFF` | 自签 `QA_RESULT`、批准自身 PR 或改变 Controller SHA |
| `A6_PUSH_CANDIDATE_BRANCH` | 只推送授权的 Candidate branch | 推送 main、修改保护设置、强推 Controller 或绕过服务器门禁 |
| `A7_CREATE_GATE_PR` | 以 `POLICY_CHANGE` 建立 `GATE_PR` 并提交完整差异和证据索引 | 自行批准、合并、发布、部署或宣告晋升完成 |

## 4. 五权分立和角色身份隔离

自举不改变 FPF 五权。五项法定职责及其边界如下：

1. **人类最高决策权（Human Sovereign）**：批准范围、代码合并、发布/部署和不可逆责任；不得由 Agent 冒名代签。
2. **负责人代理权（Owner's Delegate / Coordinator）**：在授权内编排任务、监控状态、转交证据和触发熔断；不是业务、质量或合并裁决者。
3. **架构规划权（DEV / Architect）**：审计需求、裁剪规范、提出工作令和候选实现；不得把自写自测当独立 QA，不得维护正式项目地图。
4. **独立监察权（QA / Auditor）**：独立设计测试、核验固定 SHA 和真实证据、签署 `QA_RESULT`；不得修改被测代码，不得在证据不足时 PASS。
5. **事实记账权（Scribe）**：依据已合并事实和可信 QA 证据维护唯一项目地图；不得代下技术或质量结论，不得合并自己发起的地图 PR。

协调器只是流程驱动器和中立 Trusted Evaluator 的调用方，不是第六权（coordinator-not-sixth-power）。它只能依规则计算和转发状态，不能授予权限、批准 QA、改变 `allowed_paths`、合并代码、激活 Candidate 或替代人类主权。DEV、QA、Scribe、Coordinator 和人类的身份、凭据、工作区及签名不得在同一主体中合并；尤其禁止 DEV 自审、Candidate 自批和 Scribe 代替技术审查。

## 5. 任务树与授权派生规则

### 5.1 父 Mandate 约束

每个子任务必须引用唯一父任务、父 `baseline_sha` 和父授权记录。父 mandate only narrows：父授权向子任务派生时，子任务的 `allowed_paths` 只能是父集合的子集，`allowed_actions` 只能是父集合的子集，预算不能增加，有效期不能延长，目标环境不能升级为父授权之外的环境；`forbidden_paths` 和上位安全禁令继续有效。

子任务不能通过改写 YAML、聊天摘要、重命名路径、拆分 Worktree、重新创建令牌或自行生成子任务来扩大任何一项权限。父任务未授予的 branch、Secrets、Runner、审批、部署、合并、地图或运行时控制权不会因派生而出现。需要扩大范围时必须停止当前链路，由人类签发新的范围授权，并重新进行独立 Admission；Candidate 和 Coordinator 都不能自授扩大。

### 5.2 任务树和交接

任务树中的每个节点必须保留目标、父子关系、固定 SHA、执行身份、Worktree、命令、退出码、证据路径、`not_run` 边界和结果。子节点只能回传候选输出与证据，不能直接改变父节点状态或越过 `QA_ADMISSION`、`GATE_PR`、人类合并和地图闸门。任务树账本缺失、分叉不明或收据不能重算时，整个子树保持 `BLOCKED`。

## 6. 自我修改风险分级和特殊审查

所有自举变更必须先归入以下三类风险，不能以普通功能名掩盖治理影响：

| 风险类别 | 典型范围 | 最低审查要求 |
| --- | --- | --- |
| **R1 普通功能** | 独立业务功能、展示或数据处理，不改变 Runtime、协调或治理规则 | 受限 DEV、`DEV_HANDOFF`、固定 SHA 的独立 QA 和真实测试；不得触碰受保护路径 |
| **R2 Runtime / 协调核心** | Runtime、Coordinator、任务状态、派发、取消、恢复、证据收集或执行隔离 | 独立 Admission、固定 SHA、对抗/集成测试、真实环境证据、身份和权限隔离核验；未覆盖边界必须 `NOT_RUN` |
| **R3 治理 / 授权 / QA / 合并规则** | `protected.py`、协议、分支保护、CODEOWNERS、Secrets、Runner trust root、QA 身份、审批条件或合并门禁 | `POLICY_CHANGE` → `GATE_PR`，完整实际 Diff、独立 QA、真实 QA Artifact、第二名独立审查者和人类合并；不得使用 Candidate 自审或文字豁免 |

本 Issue 的协议文件和 `packages/fpf_policy/protected.py` 属于 R3。普通 `DEV_HANDOFF` / `CODE_PR` 修改协议路径必须被拒绝；对应 `POLICY_CHANGE` 必须进入 `GATE_PR`。`sovereign_override` 不能替代独立 QA、真实证据、第二名独立审查者或人类合并。风险等级、路径范围、身份冲突或信任根无法核验时，按更高等级处理并停止。

Candidate 无论属于哪一类，都不能修改 GitHub branch protection、`CODEOWNERS`、`Secrets`、Runner trust root 或自己的 approval conditions；这些是 R3 的外部信任根和人类管理边界。若必须改变，应另立人类授权的治理任务，不得借本 Candidate 任务顺带变更。

## 7. 执行环境、凭据、分支、Worktree、状态账本和证据隔离

### 7.1 物理隔离

Controller、Candidate DEV 和独立 QA 必须使用可识别且互不复用的 branch、Worktree、进程/用户边界和 execution environment。Candidate 的工作区以 `controller_sha` 为起点；QA 使用可信工具链和同一被测 SHA 的新鲜检出，不读取 DEV 的未提交文件、缓存、凭据或临时产物。任何共享目录必须是只读或经过内容哈希核验的交换区。

### 7.2 凭据与信任根

Controller 管理凭据、Secrets、分支保护管理权限、CODEOWNERS 管理权限、QA 签署身份和 Runner trust root 不得挂载到 Candidate。Candidate 只能拿到由父 mandate 派生、最小范围、可撤销且有时效的执行凭据；凭据泄露、范围不明、无法撤销或跨环境复用时立即熔断。Candidate 不能签署自己的 `QA_RESULT`、批准自己的 PR、改变自己的 approval conditions 或为自己制造独立身份。

### 7.3 状态和证据

状态账本必须记录父任务、固定 SHA、实际 diff、分支和 Worktree、命令及退出码、执行身份、时间、`QA_RESULT`、`not_run`、失败原因和恢复动作。真实证据清单中的每个文件都必须可读取、可重算 SHA-256，并绑定被测 commit；证据清单缺失、被覆盖、与实际文件不一致或只存在聊天文本时，结论只能是 `BLOCKED` / `NOT_RUN`。

## 8. Candidate 晋升条件、兼容性、迁移与回滚

### 8.1 晋升条件

Candidate N+1 只有同时满足以下条件，才可请求晋升：

- Controller N 的 `baseline_sha` 是候选 `tested_code_sha` 的可信祖先，且 Controller SHA、PR HEAD、DEV `tested_code_sha`、QA `tested_sha` 精确一致；
- 实际 Git diff 与 `DEV_HANDOFF`、`POLICY_CHANGE` 卡片逐项一致，且严格限制在本次 `allowed_paths`；
- 独立 QA 使用可信工具链真实执行并签署 `QA_RESULT: PASS`，所有必须检查退出码为零，真实 QA Artifact 和物理哈希可重算；
- `NOT_RUN` 明确列出未执行边界，未执行内容不得被隐含地算作 PASS；P0/P1、身份重叠、权限越界、证据篡改和未知状态均未解决；
- R3 变更已由生产策略分类为 `POLICY_CHANGE` → `GATE_PR`，取得第二名独立审查者，并满足现行服务端门禁；
- 人类已在第二个人类主权闸门明确批准代码合并和候选晋升。没有人类授权时，即使 CI、QA 和审查均为绿，也只能停在等待状态。

### 8.2 兼容性和迁移

激活前必须验证 Controller N 的输入、交接卡、证据、状态账本、权限边界和回滚路径仍兼容。涉及 schema、状态、凭据或数据迁移的变更必须提供可复核的向后兼容/迁移和失败恢复证据；本协议本身不授权修改现行 Schema、状态机、授权算法、QA 身份规则或部署流程。无法验证兼容性就保持 `NOT_RUN`，不能以“理论兼容”宣告激活。

### 8.3 回滚

晋升后若观察发现错误、越权、兼容性破坏或证据异常，必须停止 Candidate、保留日志和证据、撤销 Candidate 凭据，并在人类授权下恢复到已知良好 Controller SHA。回滚目标、操作人、时间、实际 commit 和恢复后验证必须写入账本；恢复 Controller 不等于批准 Candidate，也不允许 Candidate 重新夺取控制权。自动 rollback 只能作为受控建议，不能绕过人类恢复授权。

## 9. 失败、未知状态、停止条件和人工接管

### 9.1 Failure fuse

以下任一情况触发 failure fuse：Candidate 访问 Controller 管理凭据；修改 Controller 或执行环境；扩大父 mandate；触碰未授权路径；修改分支保护、CODEOWNERS、Secrets、Runner trust root 或自身审批条件；DEV/QA 身份冲突；固定 SHA 不一致；独立 QA、第二审查、真实证据或服务端门禁缺失；无法确认人类合并授权；或出现异常进程、越界网络写入和证据篡改。熔断后不得自动重试越过失败，不得删除原始证据，不得把失败改写为成功。

### 9.2 未知状态和停止条件

超时、网络中断、Runner 状态不明、测试进程仍可能运行、取消未获终止确认、依赖版本不明或证据读取失败都属于未知状态。未知状态必须保留为 `UNKNOWN` / `NOT_RUN` / `BLOCKED`，不得释放预算、自动晋升或推断为 PASS。达到预算、重试上限、有效期、权限边界或证据完整性无法确认时，立即停止并等待人类接管。

### 9.3 人工接管与恢复

人工接管的最小步骤是：冻结 Candidate 写入；保存当前 Controller SHA、Candidate SHA、Worktree、账本和物理证据；撤销或隔离 Candidate 凭据；核对实际 diff 和分支保护；由人类选择继续、返工、回滚或废弃；恢复后重新走独立 QA 和人类闸门。Coordinator 只能报告和执行已授权的机械步骤，不能在接管时替人类决定合并、晋升、发布或地图记账。

## 10. L1/L2/L3 能力等级及禁止夸大成熟度的声明规则

### 10.1 三个成熟度等级

- **L1 单切片**：在一个固定 Controller SHA 下，完成一个受限 Candidate slice 的设计、隔离 DEV、固定 SHA 独立 QA、真实证据和人类合并；不代表可无人值守自举。
- **L2 Feature 多切片**：在 L1 约束下协调同一 Feature 的多个有父子 mandate 的切片，仍逐切片固定 SHA、独立 QA、真实证据和人类门禁；不代表可修改自身治理或自动晋升。
- **L3 多项目组织自治**：跨项目组织 Candidate 队列、隔离工位、可信 Runner、凭据撤销、故障恢复和人类监督；仍受五权、三道全局主权门、固定信任根和服务端保护约束，不能成为第六权。

### 10.2 声明规则与本任务边界

规划、设计说明、Mock、模拟工位、单元测试、聊天结论、CI 绿灯或协议文件合并都不能单独证明 L1、L2 或 L3 的真实 Runtime autonomy。若真实分支/Worktree/进程隔离、跨进程凭据撤销、真实取消终止、自动晋升、激活和回滚演练没有实际执行，必须逐项写 `NOT_RUN`，不得使用“已实现”“已具备”“全链路自治”等表述。

本 Issue 只交付制度文本、`protected.py` 的精确路径保护和回归测试，不实现 runtime autonomy，不合并、不发布、不部署、不激活 Candidate N+1。该协议文件纳入 `EXACT` 后，路径归一化的 `is_protected`、`pre_handoff`、`pr_gate` 和 `hook_guard_dev` 才能共同提供最小代码级防线；最终制度生效仍以独立 QA、真实证据、`GATE_PR`、第二独立审查和人类主权决定为准。
