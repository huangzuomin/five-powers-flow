# Five-Powers-Flow (FPF) ｜ 五权分立人机协同自治软件工程框架

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Specification](https://img.shields.io/badge/Spec-RFC--001%20v1.0-green.svg)](docs/SPECIFICATION.md)
[![Status](https://img.shields.io/badge/Status-Production%20Proven-brightgreen.svg)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

> **"DEV 交付 ≠ QA 通过 ≠ 批准合并 ≠ 批准部署"**  
> 一套基于分权制衡思想、面向多智能体（Multi-Agent）与人类深度协同的高可信、防幻觉、自驱动软件交付框架。

---

## 📖 为什么需要五权分立？(Why Five Powers?)

当前绝大多数 AI 编程工具与多智能体框架（如单体 Agent、黑盒流水线）在面对真实复杂的工业级生产项目时，普遍暴露了四大死穴：

1. **自导自测与假阳性自欺**：同一个 Agent 既负责写代码，又负责跑测试，倾向于篡改测试用例或在纯内存 Mock 中宣告“全部通过”，掩盖了真实的集成缺陷与语法崩溃。
2. **状态漂移与上下文爆炸**：单个长对话线程随着轮次增加迅速失去记忆或产生幻觉，缺乏唯一的、不可篡改的事实源（Single Source of Truth）。
3. **环境污染与并发冲突**：多个 Agent 在同一个工作区直接修改文件，没有物理隔离的工作树与独立运行环境，测试遗留的脏数据与端口冲突频发。
4. **责任主体缺位与失控越权**：要么陷入“每走一步都需要人类点确认”的高摩擦低效陷阱，要么走向“AI 擅自向主干推送甚至部署上线”的失控深渊。

**Five-Powers-Flow (FPF)** 的核心哲学：**将政治学中的权力分立制衡机制与现代严肃软件工程纪律代码化**。  
通过将人类意图、架构设计、独立质检、事实记账与中立调度彻底解耦，在保证**物理环境隔离**与**端到端硬核证据链闭环**的前提下，让异构智能体群实现**无人值守连续交付**，同时确保人类保留最终主权。

---

## 🏛️ 五权分立治理架构 (Governance Architecture)

在实际工程落地中，系统被严格解耦为**五大治理权力**与**一条中立调度总线**：

```
                           ┌──────────────────────────────┐
                           │      ① 人类最高决策者        │
                           │       (Human Sovereign)      │
                           │   [最高主权] 合并/部署/终极责任 │
                           └──────────────┬───────────────┘
                                          │ 战略授权 / 终审简报
                           ┌──────────────▼──────────────┐
                           │      ② 负责人代理 Agent      │
                           │     (Owner's Delegate)       │
                           │   [代理行政权] 目标推进/异常熔断  │
                           └──────────────┬───────────────┘
                                          │ 派发切片 / 验收案卷
  ┌───────────────────────────────────────┴───────────────────────────────────────┐
  │                                                                               │
┌─▼──────────────────┐                 ┌────────────────────┐                 ┌───▼────────────────┐
│   ③ DEV 总指挥     │                 │    ④ QA 总指挥     │                 │   ⑤ 项目地图总控   │
│ (System Architect) │                 │(Independent Auditor│                 │ (Truth & Ledger)   │
│ [架构规划权]       │                 │ [独立监察权]       │                 │ [事实记账权]       │
│ 需求审计/工作令签发│                 │ 入场门禁/独立具名裁决│                 │ 唯一正式地图/纯文档│
└─────────┬──────────┘                 └─────────┬──────────┘                 └───▲────────────────┘
          │                                      │                                │
          │ 签发工作令                           │ 具名裁决                       │ 核验证据后提议
          └──────────────────┬───────────────────┴────────────────────────────────┘
                             │
     ════════════════════════╪═══════════════════════════════════════════════════
                             │ 事件流转与状态触发
     ┌───────────────────────▼──────────────────────────────────────────────────┐
     │                ★ 协调与指令转发 Agent (Coordinator & Relay Bus)            │
     │      [无裁决权的调度中枢] 常驻轮询 / 状态机驱动 / 通道适配 / 工位生命周期       │
     └───────┬──────────────────────────────────────────────────────────┬───────┘
             │ 派发编码                                                 │ 派发验证
     ┌───────▼──────────────┐                                   ┌───────▼──────────────┐
     │    DEV 独立工位      │                                   │     QA 独立工位      │
     │ 独立 Worktree 编码自测 │                                   │ 物理隔离 0% Mock 独立复验│
     └──────────────────────┘                                   └──────────────────────┘
```

### 五权分立法定矩阵

| 治理权力 | 载体推荐 | 核心权责 | 法定红线（严禁越界） |
| :--- | :--- | :--- | :--- |
| **① 最高决策权**<br>*(Sovereign)* | **人类负责人**<br>(Human) | 战略准入批准、代码合并入主干（Merge）、部署（Deploy）、最终法律与商业责任承担。 | **严禁自动化代签**；不可逆决断权绝不下放。 |
| **② 代理行政权**<br>*(Delegate)* | **Codex 总协调代理**<br>(Owner's Agent) | 继承人类授权推进切片队列、资源与 Token 监控、异常熔断挂起、生成“双 PR 红绿简报”。 | **严禁私自修改主干**；严禁替 QA 签署测试结论。 |
| **③ 架构规划权**<br>*(Architect)* | **ChatGPT/Claude 线程**<br>(Planner) | 需求审计、规格裁剪、签发 DEV 工作令（Work Order）、初审开发自测报告。 | **严禁自写自测后冒充独立 QA**；严禁修改正式地图。 |
| **④ 独立监察权**<br>*(Auditor)* | **独立上下文 AI 线程**<br>(Auditor) | 入场门禁审查（Admission）、设计红绿对抗用例、核验 32 项原始日志、出具法定裁决（PASS/FAIL）。 | **严禁修改被测业务代码**；严禁在 Mock 中自嗨。 |
| **⑤ 事实记账权**<br>*(Scribe)* | **项目地图专项线程**<br>(Ledger) | 维护全局唯一项目进度地图（`PROJECT-MAP.md`）；核验独立 QA 报告后发起纯文档 PR。 | **严禁代下技术结论**；严禁合并自己提起的文档 PR。 |

---

## ⚙️ 核心工程机制 (Key Engineering Mechanisms)

### 1. 物理环境与工位隔离 (Physical Workspace Isolation)
- **Git Worktree 隔离**：DEV 与 QA 拥有完全独立的物理路径，互不干扰，禁止共用脏工作树。
- **环境自给自治**：QA 工位自动分配随机端口、临时独立测试数据库与干净依赖，随测随建，跑完即毁。

### 2. 0% Mock 真实性与对抗验证 (Zero-Mock & Red-Check)
- **拒绝 Mock 自欺**：严禁把内存 Mock、CI 静态检查等同于 QA 通过。核心数据流必须经过真实数据库、真实 API 与真实浏览器（Playwright）端到端回归。
- **红绿对抗反证 (Red Check)**：在缺陷修复轮次中，强制执行变异测试——将修复代码回退至旧版本时，测试用例必须能够确凿失败（退出码非 0），杜绝空跑测试。

### 3. 错题本制度 (Lessons-Learned & Seen 3× Rule)
- 设立仓库级 `LESSONS.md`。DEV 总结、QA 背书、人类核准。
- **Seen 3× 自动晋升**：同一类缺陷在不同切片中出现 3 次，**强制自动晋升为 CI 自动化对抗门禁用例**，从源头截断复犯可能。

### 4. 双 PR 独立制衡机制 (Dual-PR Checks & Balances)
- 代码变更有**代码 PR**（DEV 发起），进度记录有**地图 PR**（地图总控根据 QA 证据发起）。
- 严禁代码 PR 夹带修改项目地图；负责人通过中枢提炼的“红绿简报”，一次审阅，两次点击（Merge Code + Merge Map），兼顾权力分立与极简体验。

---

## 🔄 切片顺位流转生命周期 (Slice Lifecycle)

```text
[人类或代理者批准切片]
       │
       ▼
[DEV 总指挥出具最小 Spec 与工作令]
       │
       ▼
[DEV 工位 Worktree 隔离编码 ➔ 自测门禁 ➔ 提测 PR ➔ 签发 DEV_HANDOFF]
       │
       ▼
[协调中枢感知 DEV_READY ➔ QA 总指挥审查入场门禁]
       │
       ▼ (Admission PASS)
[QA 工位独立 Worktree 启动 ➔ 真实无 Mock 回归 ➔ 生成 32 项证据包与 SHA-256 主锚点]
       │
       ▼
[QA 总指挥出具具名法定裁决 (QA_RESULT: PASS / FAIL)]
       │
       ├─────────────────────────────────┐
       ▼ (PASS)                          ▼ (FAIL / INVALID_TEST)
[地图总控提议纯文档 PR]           [打回 DEV 工位重新修复]
       │
       ▼
[中枢呈送人类终审简报 ➔ 人类负责人两次确认合并]
       │
       ▼
[工位资源清理 ➔ 自动流转下一切片]
```

---

## 🚀 快速开始 (Quick Start)

### 1. 安装脚手架 (规划中)
```bash
pip install five-powers-flow
# 或者通过 npx / cargo
```

### 2. 在现有项目中植入 FPF 规范
```bash
cd your-project
fpf init --vcs github
```
这将在当前工程中生成标准骨架：
- `docs/coordination/`：植入规范协议、单一事实地图模板、错题本模板。
- `AGENTS.md`：注入智能体法定边界与行为红线。
- `.github/`：植入切片追踪 Issue 模板与 PR 契约门禁。

### 3. 启动中立协调守护进程
```bash
fpf-coordinator start --repo your-org/your-repo --poll-interval 30
```

---

## 📂 仓库结构 (Repository Layout)

```text
five-powers-flow/
├── README.md                           # 本说明文档
├── LICENSE                             # Apache 2.0 开源许可证
├── CONTRIBUTING.md                     # 开源贡献指南
├── CODE_OF_CONDUCT.md                  # 行为准则
├── SECURITY.md                         # 安全策略
├── docs/
│   ├── SPECIFICATION.md                # FPF-RFC-001 协议规范完整条令
│   └── ARCHITECTURE.md                 # 深度架构设计与状态机模型
├── schemas/                            # 机器可读的 JSON / YAML 契约规范
│   ├── work-order.schema.json          # 架构工作令 Schema
│   ├── dev-handoff.schema.json         # 研发交付卡 Schema
│   ├── qa-result.schema.json           # 质检裁决卡 Schema
│   └── coordination-ledger.schema.json # 调度协调账本 Schema
├── templates/                          # 开箱即用的项目模板套件
│   ├── AGENTS.md.template              # 通用仓库智能体红线规范
│   ├── PROJECT-MAP.md.template         # 单一项目地图模板
│   ├── LESSONS.md.template             # 错题本制度模板
│   └── HANDOFF-PROTOCOL.md.template    # 项目交接协议模板
├── packages/                           # 核心工具链与引擎实现 (WIP)
│   ├── fpf-core/                       # 状态机与契约验证器
│   ├── fpf-coordinator/                # 中立轮询调度中枢守护进程
│   └── fpf-gates/                      # 交付前预检与 Manifest 生成器
└── .github/                            # 开源协作与 CI 模板
```

---

## 🤝 参与贡献 (Contributing)

我们非常欢迎来自开源社区的实践者共同完善五权分立人机协同自治体系！  
请阅读我们的 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何提交 RFC、改进适配器与丰富错题集。

## 📜 许可证 (License)

本项目采用 [Apache License 2.0](LICENSE) 开源协议。
