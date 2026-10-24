# Five-Powers-Flow (FPF) ｜ 五权分立人机协同自治软件工程框架

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Specification](https://img.shields.io/badge/Spec-RFC--001%20v1.2.1-green.svg)](docs/SPECIFICATION.md)
[![Status](https://img.shields.io/badge/Status-RFC%20Spec%20%26%20Reference%20Tooling-blue.svg)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

> **"DEV 交付 ≠ QA 通过 ≠ 批准合并 ≠ 批准部署"**  
> 一套基于分权制衡思想、面向多智能体（Multi-Agent）与人类深度协同的高可信、防幻觉、自驱动软件交付框架。  
> **以 GitHub 为唯一法定事实源，以代码 Hook 与物理隔离实现机械强制约束。**

---

## 📖 为什么需要五权分立？(Why Five Powers?)

当前绝大多数 AI 编程工具与多智能体框架在面对真实复杂的工业级生产项目时，普遍暴露了四大死穴：

1. **自导自测与假阳性自欺**：同一个 Agent 既负责写代码，又负责跑测试，倾向于篡改测试用例或在纯内存 Mock 中宣告“全部通过”，掩盖了真实的集成缺陷与语法崩溃。
2. **状态漂移与上下文爆炸**：单个长对话线程随着轮次增加迅速失去记忆或产生幻觉，缺乏唯一的法定事实源（Single Source of Truth）。
3. **环境污染与并发冲突**：多个 Agent 在同一个工作区直接修改文件，没有物理隔离的工作树与独立运行环境，测试遗留的脏数据与端口冲突频发。
4. **责任主体缺位与失控越权**：要么陷入“每走一步都需要人类点确认”的高摩擦低效陷阱，要么走向“AI 擅自向主干推送甚至部署上线”的失控深渊。

**Five-Powers-Flow (FPF)** 的核心哲学：**将政治学中的权力分立制衡机制与现代严肃软件工程纪律代码化**。  
通过将人类意图、架构设计、独立质检、事实记账与中立调度彻底解耦，在保证**物理环境隔离**与**端到端硬核证据链闭环**的前提下，让异构智能体群实现**无人值守连续交付**，同时确保人类保留最终主权。

---

## 🛡️ 治理核心：从“提示词道德约束”走向“机械强制” (Mechanical Enforcement)

> **铁律**：如果分权只靠提示词告诉 LLM “你是 QA，请不要改代码”，那不是安全边界，那是祈祷。真正的隔离需要制度与物理上的**机械强制**。

1. **工具集硬剔除**：在支持的平台（如 Claude Code `Explore`/`Plan` 子代理）中，直接剔除写操作工具（`Edit`/`Write`），使规划与监察角色在物理层面无法修改代码；
2. **Pre-Push / Pre-Tool-Use 钩子拦截**：在本地 Git Hook 与工具调用层部署哨兵，**通过客户端钩子与服务端 CODEOWNERS + CI 双层阻断研发工位（DEV）向 `PROJECT-MAP.md` 窜写**（详见 [templates/git-hooks/pre-push.template](templates/git-hooks/pre-push.template)）；
3. **密码学 SHA 强一致性校验**：由中立校验脚本强制核对 `qa_card.tested_sha == dev_card.tested_code_sha`，且必须在 Git 对象库中物理存在（`git cat-file -e`），从代码层杜绝伪造验收。

---

## 🌐 GitHub 在体系中的战略定位：宪政级基础设施

在 Five-Powers-Flow 中，GitHub **绝不仅是一个代码仓库**，而是整套框架运转的**单一事实源（SSOT）与公共总线**：

```
                ┌────────────────────────────────────────────────────────┐
                │             GitHub (唯一法定事实源与总线)              │
                ├────────────────────────────────────────────────────────┤
                │  1. 跨异构 Agent 异步通信总线 (Issue/PR/Structured YAML)│
                │  2. 防篡改密码学证据链与 Git Commit 锚点 (40-digit SHA)  │
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

1. **跨异构 Agent 通信总线**：彻底解决 ChatGPT、Claude、Codex、DeepSeek 等不同厂商、无局域网互通模型之间的异步数据交换难题。所有任务令与报告均通过 GitHub Issue / PR 的标准化 YAML 卡片传递。
2. **不可篡改的法定证据链**：AI 聊天记录随时会被压缩或遗忘，但 GitHub 上的 40 位 Commit SHA、Diff 记录具备密码学不可篡改性。“聊天仅供通知，GitHub 才是法定裁判依据”。
3. **无中心数据库的状态机表面**：切片生命周期（待开发、提测中、QA审查中、待合并）直接投射为 GitHub Labels 与状态流，无需外部专用数据库。
4. **主权隔离与权限防火墙**：GitHub 分支保护规则（Branch Protection）与合并锁，从物理底层保障了“人类最高决策权不可被 Agent 篡夺”。未经人类点击 Merge，主干代码纹丝不动。
5. **物理工位的纯净克隆锚点**：DEV 与 QA 两个独立 Worktree 均以 GitHub 远端锁定的确切 Commit SHA 为基准，绝不把本地脏文件带入测试。
6. **双 PR 制衡法定执行场**：代码 PR（DEV 提）与地图 PR（地图总控提）在 GitHub 上物理分离，使“写代码者严禁自改试卷”在平台机制层面得到铁腕落实。

---

## 🏛️ 五权分立治理架构 (Governance Architecture)

| 治理权力 | 载体推荐 | 核心权责 | 法定红线（严禁越界） |
| :--- | :--- | :--- | :--- |
| **① 最高决策权**<br>*(Sovereign)* | **人类负责人**<br>(Human) | 战略准入批准、代码合并入主干（Merge）、部署（Deploy）、最终法律与商业责任承担。 | **严禁自动化代签**；不可逆决断权绝不下放。 |
| **② 代理行政权**<br>*(Delegate)* | **Codex/Orchestrator**<br>(Owner's Agent) | 继承人类授权推进切片队列、资源与 Token 监控、异常熔断挂起、生成“双 PR 红绿简报”。 | **严禁私自修改主干**；严禁替 QA 签署测试结论。 |
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

### 4. 32 项标准证据包体系 (32-Item Evidence Pack)
- 详见 [docs/EVIDENCE-SPEC.md](docs/EVIDENCE-SPEC.md)。涵盖元数据、物理环境凭证、真实 API 抓包、数据库事务断言、浏览器全图渲染与主哈希锚点，缺一不可。

---

## 🚀 快速上手 (Getting Started)

当前仓库提供完整的 **协议规范 (RFC-001)**、**数据 Schema 契约**、**机械门禁参考脚本** 与 **开箱即用模板**。

### 1. 运行本地提测前门禁 (Pre-Handoff Quality Gate)
DEV 工位在提测前，必须在本地运行门禁脚本：
```bash
python packages/fpf-gates/pre_handoff.py --base main
```
脚本将机械强制检查：
- 工作树是否完全干净（无未提交、无未受控文件）；
- 当前提交是否具备合法的 40 位 SHA；
- **是否违规触碰了 `PROJECT-MAP.md`**（违者直接退出码 1 阻断提测）。

### 2. 验证交接卡与 SHA 链条一致性
协调中枢对提测卡与质检卡进行机器级强验证：
```bash
python -m packages.fpf_coordinator.coordinator --dev-card dev_handoff.yaml --qa-card qa_result.yaml --evidence-dir docs/evidence --check-git
```
脚本将验证：
- 卡片所有必填字段与 Schema 约束；
- `not_run` 列表非空；
- **QA 验收的 `tested_sha` 是否与 DEV 提测 SHA 严格绝对一致**；
- 两个 SHA 是否在本地 Git 对象库中真实存在。

### 3. 第一个 PR 走通标准闭环 (First Walkthrough via Protocol)
1. **DEV 发起分支与开发**：在独立 worktree 或特性分支开发，本地运行 `python packages/fpf-gates/pre_handoff.py --base main`；
2. **提交代码 PR**：在 PR 描述中填入合规 `DEV_HANDOFF` 卡片；CI 自动触发并验证卡片与 SHA 绑定；
3. **QA 独立工位验收**：检出 PR 分支，执行对抗验证，输出 `docs/evidence/` 与 `manifest.json`，在评论中签署 `QA_RESULT`；
4. **人类终审与 Squash Merge**：人类负责人核查红绿简报并在 GitHub 点击 Merge，主干生成正式提交 SHA；
5. **地图总控发起地图 PR**：根据代码 commit SHA 提交包含 `MAP_UPDATE` 的纯文档 PR，经 CI 验证祖先关系后由人类合入主干。

### 4. 在你的新项目中植入规范
1. 复制 `templates/` 下的模板文件到你的工程：
   - 将 `AGENTS.md.template` 放置于仓库根目录 `AGENTS.md`；
   - 将 `PROJECT-MAP.md.template`、`LESSONS.md.template` 放置于 `docs/coordination/`；
   - 将 `templates/git-hooks/pre-push.template` 安装到 `.git/hooks/pre-push`。
2. 配置分支保护规则，锁定 `main` 分支需经人类审批。

---

## 📂 仓库结构 (Repository Layout)

```text
five-powers-flow/
├── README.md                           # 框架主说明文档
├── CHANGELOG.md                        # 语义化版本变更历史 (Keep a Changelog)
├── pyproject.toml                      # 现代化 Python 构建与测试工程元数据
├── LICENSE                             # Apache 2.0 开源许可证
├── CONTRIBUTING.md                     # 开源贡献指南
├── CODE_OF_CONDUCT.md                  # 行为准则
├── SECURITY.md                         # 安全策略
├── .github/
│   ├── CODEOWNERS                      # 服务端治理文档所有权硬锁定
│   └── workflows/
│       ├── validate-schemas.yml        # CI: 契约语法元校验与边界测试
│       └── validate-handoff-cards.yml  # CI: PR 交付卡密码学与作用域强校验
├── docs/
│   ├── SPECIFICATION.md                # FPF-RFC-001 协议规范完整条令 (v1.2.1)
│   ├── EVIDENCE-SPEC.md                # 32 项标准证据包规范 (四级分级 Profile)
│   └── CLAUDE-CODE-GUIDE.md            # Claude Code 机械强制落地指南
├── .claude/
│   └── settings.json                   # Claude Code 原生 PreToolUse 钩子治理配置
├── schemas/                            # 机器可读的 JSON / YAML 契约规范 (Draft-07)
│   ├── work-order.schema.json          # 架构工作令 Schema
│   ├── dev-handoff.schema.json         # 研发交付卡 Schema (含 not_run 矩阵与 SHA 强制)
│   ├── qa-result.schema.json           # 质检裁决卡 Schema (强制 exit_code 验证与双向 SHA)
│   ├── manifest.schema.json            # 32 项证据包清册 Schema (Profile 强制)
│   └── coordination-ledger.schema.json # 调度协调账本 Schema
├── templates/                          # 开箱即用的项目模板套件
│   ├── AGENTS.md.template              # 通用仓库智能体红线规范
│   ├── PROJECT-MAP.md.template         # 单一项目地图模板
│   ├── LESSONS.md.template             # 错题本制度模板
│   ├── HANDOFF-PROTOCOL.md.template    # 项目交接协议模板
│   └── git-hooks/pre-push.template     # 物理防窜写 Git 推送拦截钩子 (merge-base 强化)
├── tests/
│   └── test_trusted_evaluator.py       # 密码学断言与安全边界单元测试套件
└── packages/                           # 核心门禁与验证器实现
    ├── fpf_coordinator/coordinator.py  # 协调器与密码学 SHA/作用域/证据包强校验器
    └── fpf-gates/pre_handoff.py        # 交付前四道机械门禁检查器 (含敏感产物审计)
```

---

## 🤝 参与贡献 (Contributing)

我们非常欢迎来自开源社区的实践者共同完善五权分立人机协同自治体系！  
请阅读我们的 [CONTRIBUTING.md](CONTRIBUTING.md) 了解如何提交 RFC、改进适配器与丰富错题集。

## 📜 许可证 (License)

本项目采用 [Apache License 2.0](LICENSE) 开源协议。
