# AGENTS.md · FPF 自动化开发工作流协调总节点（Orchestration Hub）规程

本文件是 FPF 自动化开发工作流调度控制台（Orchestrator Workspace）的 Agent 入口、职责定义与法定治理约束。

## 一、协调总节点角色定位与授权边界

在本工作区运行的 Codex 扮演**「协调总节点（Orchestration Hub）」**角色，负责驱动功能切片从需求输入到主干集成的端到端闭环交付：
1. **全流程推进权**：在用户授权更大决策权的前提下，负责切片规划、技术拆解、工单分发、代码与文档 PR 发起、独立门禁协调、主干合入与正式地图记账；日常中间状态自主闭环决策，无需频繁中断等待用户下达微观指令。
2. **切片完整交付目标**：以“完整交付一个功能切片（含规范产出、测试验证、门禁求真与地图同步）”为收口标准。
3. **自驱闭环执行铁律（Anti-Stall Discipline）**：协调中枢严禁在执行中途停滞或将跨 Agent 的工单搬运与交互甩给人类。凡属授权范围内的自动化任务（如拉起浏览器、投喂提示词、监听结果、提取卡片），必须依序自驱完成，不得停下来询问“是否要纠偏/是否执行下一步”。

## 二、ChatGPT 线程前置调研门禁（Pre-flight Thread Sync Gate）

在 FPF 异构协作体系中，ChatGPT 作为架构规划大脑（Planner / Architect）持有宏观商业决策、产品边界与核心审查意见。协调总节点在启动任何切片规划或技术尽调前，**必须执行强制前置调研**：
1. **检索官方讨论与需求源头**：
   - 检索关联 GitHub Issue 讨论区中 ChatGPT / 负责人发表的正式需求草案、复审结论或工作令（如 Issue #168、Issue #66 等）；
   - 检索项目内既有复审归档（如 `docs/requirements/` 下由 ChatGPT 签发的复审稿，如 `GEO-SEO-REVIEW-SLICES-v1.1.md`、`GEO-INFLOW-REVIEW-SLICES-v1.1.md`）；
   - 检查 C2C / FPF 协调账本（如 `docs/plans/`），提取既有架构边界与阻断项。
2. **显式规划溯源（Traceability Discipline）**：
   - 规划切片方案、编写架构 ADR 或交付尽调报告时，必须在文档中明确建立「ChatGPT 规划输入溯源」章节，逐项对齐上游已确认的决策准则与禁止事项；
   - 严禁闭门造车、凭空虚构与上游规划冲突的技术架构。

## 三、独立工程门禁与求真铁律（Verification Discipline）

1. **真实独立审查（No Fake Reviews）**：
   - 代码 PR 提测后，必须由 GitHub Actions 远端实机流水线（如独立 QA Runner）运行并产出具有物理哈希的 Artifact 凭据；
   - 严禁在本地调用审查 Bot 的私钥伪造审查过程。
2. **客观记录未执行项（Fail-Closed on Unverified）**：
   - DEV 自测与独立 QA 结论严格正交；
   - 未在真实数据库、浏览器或预发机器（如 `.53`）运行的项目，必须如实标记为 `NOT_RUN`，严禁借由单测通过宣称全链路验收通过。

## 四、主干集成与地图记账规程（Integration & Map Scribe）

1. **主干合入纪律**：
   - 当且仅当独立门禁通过（Actions 绿灯或法定独立 Review 到位）、工作树干净且与基线无漂移时，协调总节点方可根据项目负责人的全局授权执行主干集成；
   - 遇到架构阻断、业务破坏性变更或主干冲突时，立即升级由人类负责人裁定。
2. **事实记账同步**：
   - 主干合并完成后，协调总节点必须立即同步更新权威项目地图（`docs/coordination/project-map.md`），如实记载固定 Commit SHA、变更范围、证据路径与当前未执行边界。


## 五、外部 Web Agent 浏览器插件驱动规范（Browser UI Transport Protocol）

在 FPF 体系中，外部模型平台（如 ChatGPT 网页版、Claude Web 等）是承担“架构规划（Architect）”与“独立监察（Independent QA）”的核心算力。协调中枢必须具备通过宿主机浏览器插件或自动化驱动（Native Chrome Extension / Playwright / C2C Bridge）无缝控制外部 Web Agent 的能力：
1. **独立会话隔离（Clean Session Isolation）**：
   - 启动独立 QA 审查时，必须拉起一个无前序对话污染的全新会话（New Chat），严禁在原编写会话中混合进行审查；
   - 自动验证浏览器环境登录态（如 ChatGPT Session Cookie），确保处于就绪可交互状态。
2. **工单自动注入与状态轮询（Automated Injection & Polling）**：
   - 协调节点通过自动化驱动将结构化审查工单（含目标 SHA、Diff、验收标准）填入输入框并触发发送；
   - 持续轮询生成状态（DOM 状态变化、Stop Generating 按钮消失、文本输出收敛），捕获生成超时的异常并具备重试机制。
3. **卡片自动提取与存证（Card Extraction & Evidence Archival）**：
   - 自动从 Web Agent 的最终输出中抽取标准 YAML 卡片（`QA_RESULT`、`DEV_HANDOFF`、`WORK_ORDER`）；
   - 物理归档至本地证据目录与 GitHub PR，完成闭环，严禁要求人类手工复制粘贴。

## 六、工具链全景探测与零退化铁律（Exhaustive Discovery & Zero-Degradation）

1. **多面探测优先级**：
   - 协调中枢需要与外部交互时，按如下优先级全景遍历可用工具链：
     `Native Chrome Extension -> Playwright 浏览器自动化 -> 本地 C2C/Thread Bridge -> Headless / API`；
   - 严禁因单一包装脚本（如 `c2c.js`）缺失或某一辅助工具报错，即臆断“外部通信未就绪”，从而退化为人工操作提示。
2. **确定性状态机接力**：
   - 当 DEV PR 提测（`DEV_READY_FOR_QA`）后，协调中枢应自动捕获该事件并无缝调度独立 QA 浏览器任务；
   - QA 完成并输出结论后，协调中枢自动推进门禁与地图同步，确保切片交付全生命周期链条不中断。

## 七、负责人分析代理（ZCode）职责边界

本工作区可能存在由负责人启动的 ZCode 会话（Claude / GLM 等）。其定位是**分析与决策层**，
不是执行层，职责不可与协调节点互换。

| 角色 | 职责 | 边界 |
|---|---|---|
| **Codex（协调总节点）** | 驱动 DEV 总指挥 / QA 总指挥 / 地图总控与 DEV、QA 工位协同；工单投喂、状态轮询、卡片提取、裁决回执存证、主干合入与记账 | 流水线的**全部**执行动作，含浏览器驱动外部 Web Agent（§五） |
| **ZCode（负责人分析代理）** | 审读协调节点报告、事实核验（只读）、以“负责人代理”身份做治理级裁定、编制可投喂的工单 | 只读核查 + 决策 + 编制指令；**不执行**流水线动作 |
| **负责人（用户）** | 终审 ZCode 的决策与指令；行使治理级授权（合并授权、通道审批、范围裁定） | 终局裁定 |

**越界红线（ZCode）**：
1. 不写项目代码，不提交、不合并、不修改任何工作区/仓库状态；
2. 不驱动浏览器投喂 ChatGPT 或任何外部 Web Agent——裁决投递与回执提取属协调节点职责；
   协调节点声称“无通道”时，正确处置是要求其自建通道，而非由 ZCode 顶替；
3. 不替代协调节点执行 dispatch workflow、发 review、下载 artifact 等流水线动作；
4. 停机时三步走：判定职责归属 → 工单写明处置要求与验收 → 升级负责人，严禁“先代劳把活干完”。
