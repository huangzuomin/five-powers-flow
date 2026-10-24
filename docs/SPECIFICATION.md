# Five-Powers-Flow Specification (FPF-RFC-001)

> **版本**：v1.2.1 (RFC Spec & Reference Implementation) · [变更历史](../CHANGELOG.md)  
> **分类**：治理与工程协议标准  
> **核心宪章**：$\text{DEV 交付} \neq \text{QA 通过} \neq \text{批准合并} \neq \text{批准部署}$  
> **定位澄清**：本协议确立治理权力边界、不可伪造证据要求与状态机规范。本阶段为实验性参考规范，需配合服务端权限策略与可信验证器运行。

---

## 1. 范围与目标 (Scope & Objective)

本协议旨在规范多智能体（Multi-Agent System）与人类软件工程师协同开发复杂软件系统时的**权力边界、状态迁移契约、环境隔离与审计存证标准**。

在传统的单体 Agent 或闭环多智能体框架中，智能体间通信多依赖内存上下文或私有数据库，极易出现幻觉篡改、自导自测、上下文爆炸与责任失控。本协议以现代版本控制平台（以 GitHub 为基准）为物理与逻辑总线，确立高可信自驱动交付规范。

---

## 2. GitHub 的战略定位与核心作用 (The Strategic Role of GitHub)

在 Five-Powers-Flow 体系中，GitHub **绝不仅是一个代码托管仓库**，它是整套五权分立自动化得以运转的**公共通信媒介与存证总线**：

```
                ┌────────────────────────────────────────────────────────┐
                │             GitHub (唯一法定事实源与总线)              │
                ├────────────────────────────────────────────────────────┤
                │  1. 跨异构 Agent 异步通信总线 (Issue/PR/Structured YAML)│
                │  2. 不可篡改的证据链与 Git Commit 锚点 (40-digit SHA)  │
                │  3. 无数据库的公开状态机 (Labels & Lifecycle Tracking) │
                │  4. 主权隔离与权限物理防火墙 (Branch Protection & Merge)│
                │  5. 物理工位纯净克隆锚点 (Git Worktree Base)           │
                │  6. 双 PR 制衡法定执行场 (Code PR vs Map PR)           │
                └───────────────────────────▲────────────────────────────┘
                                            │ 读写数据与事件触发
    ┌──────────────────────┬────────────────┼──────────────────────┬──────────────────────┐
    │                      │                │                      │                      │
┌───┴──────────┐   ┌───────┴──────┐   ┌─────┴────────┐   ┌─────────┴────┐   ┌──────────────┴───────┐
│ ① 人类决策者 │   │ ② 代理 Agent │   │ ③ DEV 总指挥 │   │ ④ QA 总指挥  │   │ ⑤ 项目地图总控       │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘   └──────────────────────┘
```

### 2.1 跨异构 Agent 异步通信总线 (Universal Asynchronous Message Bus)
- **破除厂商壁垒**：参与项目的智能体往往来自不同模型平台（如 ChatGPT 网页版、Claude CLI、本地 Codex、DeepSeek 专有模型等），它们之间无局域网互通、无跨厂商 RPC。
- **全异步可靠载体**：GitHub Issue、PR 描述、Issue 评论（Comment）是所有 Agent 唯一允许交换任务与结果的媒介。所有通信均采用标准的 `WORK_ORDER`、`DEV_HANDOFF`、`QA_RESULT` 结构化 YAML 区块，自带时间戳，异步持久化，永不丢失。

### 2.2 不可篡改的法定证据链 (Tamper-Evident Canonical Ledger)
- **对抗上下文压缩与遗忘**：聊天上下文会随着对话轮次增加被自动 Compact 或发生模型幻觉，但 GitHub 上的 Git Commit、代码 Diff、提交记录具备密码学哈希保证（40 位 SHA）。
- **口说无凭，Git 证据为准**：任何 Agent 宣称“功能已完成”或“测试已通过”，若不能在 GitHub 对应 PR 中提供确凿的 40 位 Commit SHA 及可重放日志引用，一律视为无效陈述。

### 2.3 无中心数据库的状态机表面 (Database-less Public State Machine)
- 整个自驱动流水线无需维护专用的外部中心数据库或分布式协调器。
- 切片的生命周期状态（`pending-dev` $\rightarrow$ `dev-ready` $\rightarrow$ `qa-reviewing` $\rightarrow$ `qa-passed` $\rightarrow$ `awaiting-merge`）直接投射为 GitHub Issue/PR 的 **Labels、状态标记与评论流**。协调器通过轮询 GitHub 即可完成 100% 确定性的状态判定。

### 2.4 主权隔离与权限物理防火墙 (Constitutional Sovereign Firewall)
- **代码不可侵犯闸门**：GitHub 的 **分支保护规则 (Branch Protection Rules)** 与 **强制审查 (Required Reviews)**，是物理上锁死“人类最高决策权不可被 Agent 篡夺”的最后防线。
- 无论 Agent 自我宣称多么完美、测试多么绿灯，只要人类未在 GitHub 网页或客户端点击 **Confirm Merge**，受保护的 `main` 分支物理上坚不可摧，彻底杜绝 AI 擅自合并和污染生产代码。

### 2.5 物理工位环境纯净锚点 (Clean Workspace Anchor)
- DEV 工位和 QA 工位各自拉取独立的 Git Worktree，其代码基线完全以 GitHub 远端推送的确定性 SHA 为锚点。
- QA 独立工位验证的代码，必须是 DEV 已经推送到 GitHub 远端 PR 的确切版本，绝不测试 DEV 电脑上的本地脏暂存，确保验证结果 100% 可被第三方复现。

### 2.6 双 PR 制衡法定执行场 (Dual-PR Separation Field)
- **代码 PR**（DEV 发起）包含业务代码与自测代码；**地图 PR**（地图总控发起）仅修改 `docs/coordination/PROJECT-MAP.md`。
- GitHub 的 PR 分离机制物理上杜绝了 DEV 智能体在提交代码时“顺手修改项目地图宣布完工”的自改试卷行为。

---

## 3. 治理五权与可信裁决器规范 (Five Powers & Trusted Evaluator)

必须明确：**状态的最终跃迁绝不依赖 Agent 自然语言的自述，而是必须由可信裁决器（Trusted Evaluator）依据真实证据计算得出。**

### 3.1 ① 人类最高决策者 (Human Sovereign)
- **法定权力**：业务范围授权、在 GitHub 上执行代码合并入主干（Merge）、正式部署上线、商业与法务最终决策。
- **法定禁令**：不得由任何 Agent 冒名代签；不得将不可逆的操作权限交由自动化推定。

### 3.2 ② 负责人代理 Agent (Owner's Delegate)
- **法定权力**：在人类既定授权内推进任务序列；监控执行工位的运行与 Token 消耗；检测到异常、死锁或越界时触发熔断保护；生成“双 PR 红绿简报”。
- **法定禁令**：未经人类明示授权，严禁对主干执行 Merge 或部署；严禁替 QA 签署测试结论。

### 3.3 ③ DEV 总指挥 (System Architect)
- **法定权力**：切片范围审计与架构设计；裁剪出最小 Spec；在 GitHub Issue 下签发标准 DEV 工作令（Work Order）；审核 DEV 工位交付物的完整性。
- **法定禁令**：严禁自写自测后宣称通过独立质检；严禁直接修改正式项目地图；严禁发起主干合并。

### 3.4 ④ QA 总指挥 (Independent Auditor)
- **法定权力**：审核切片提测入场门禁（Admission Gate）；独立设计对抗用例与真实业务消融；核验原始测试日志与哈希锚点；出具法定裁决卡片（`PASS` / `FAIL` / `BLOCKED` / `INVALID_TEST`）。
- **法定禁令**：严禁修改被测业务代码；严禁在存在 P0 缺陷时签署 PASS；严禁脱离 DEV 卡片出具孤立验收。

### 3.5 ⑤ 项目地图总控 (Truth & Ledger Scribe)
- **法定权力**：维护仓库唯一正式项目地图（`PROJECT-MAP.md`）；根据可信裁决器计算出的正式 PASS 结果提出纯文档 PR。
- **法定禁令**：严禁代下技术或质量结论；严禁在缺乏独立 QA 凭据前登记完工；严禁直接合并自己发起的文档 PR。

### 3.6 ★ 中立协调与可信裁决器 (Coordinator & Trusted Evaluator)
- **属性**：中立、无业务裁决权的状态机执行器与密码学强校验引擎。
- **计算职责**：
  1. 物理检查 DEV 提测 SHA 与 QA 验收 SHA 严格一致（`tested_sha == tested_code_sha`）；
  2. 物理检查 SHA 在 Git 对象库中必须属于 `commit` 类型对象；
  3. 物理读取 `manifest.json` 并重新计算 SHA-256 哈希，核对是否与卡片一致；
  4. 检查是否存在未解决的 `findings.p0` 缺陷；
  5. 只有上述所有检查全部无误，才计算输出 `QA_PASSED_AWAITING_OWNER_MERGE` 状态。

---

## 4. 双 PR 原子顺序与防漂移规则 (Dual-PR Ordering & Anti-Drift)

为消灭“代码 PR 尚未合并、地图 PR 先行合并导致状态漂移”的重大隐患，协议强制确立以下顺序与绑定约束：

1. **严格合并次序 (Strict Sequential Merging)**：
   - **第一步**：人类负责人必须先合并**代码 PR**，在主干生成确定的 `MERGE_COMMIT_SHA`；
   - **第二步**：地图总控获取该主干 `MERGE_COMMIT_SHA`，写入 `PROJECT-MAP.md` 的归档凭据中；
   - **第三步**：人类负责人合并**地图 PR**。
2. **禁止颠倒次序**：服务端 CI 门禁将物理检查：若对应的代码 PR 尚未合并，地图 PR 严禁合并。
