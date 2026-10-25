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
                │  2. 可检测篡改的证据链与 Git Commit 锚点 (40-digit SHA)  │
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
- **全异步可靠载体**：GitHub Issue、PR 描述、Issue 评论（Comment）是所有 Agent 唯一允许交换任务与结果的媒介。所有通信均采用标准的 `WORK_ORDER`、`DEV_HANDOFF`、`QA_RESULT`、`MAP_UPDATE` 结构化 YAML 区块，自带时间戳，异步持久化，由平台持久保存（仍需备份及权限保护）。

### 2.2 可核验的证据锚点 (Tamper-Evident Canonical Ledger)
- **对抗上下文压缩与遗忘**：聊天上下文会随着对话轮次增加被自动 Compact 或发生模型幻觉，但 GitHub 上的 Git Commit、代码 Diff、提交记录具备密码学哈希保证（40 位 SHA）。
- **口说无凭，Git 证据为准**：任何 Agent 宣称“功能已完成”或“测试已通过”，若不能在 GitHub 对应 PR 中提供确凿的 40 位 Commit SHA 及可重放日志引用，一律视为无效陈述。

### 2.3 无中心数据库的状态机表面 (Database-less Public State Machine)
- 整个自驱动流水线无需维护专用的外部中心数据库或分布式协调器。
- 切片的生命周期状态（`pending-dev` $\rightarrow$ `dev-ready` $\rightarrow$ `qa-reviewing` $\rightarrow$ `qa-passed` $\rightarrow$ `awaiting-merge`）直接投射为 GitHub Issue/PR 的 **Labels、状态标记与评论流**。协调器通过轮询 GitHub 即可完成 100% 确定性的状态判定。

### 2.4 主权隔离与权限物理防火墙 (Constitutional Sovereign Firewall)
- **代码不可侵犯闸门**：GitHub 的 **分支保护规则 (Branch Protection Rules)** 与 **强制审查 (Required Reviews)**，是物理上锁死“人类最高决策权不可被 Agent 篡夺”的最后防线。
- 无论 Agent 自我宣称多么完美、测试多么绿灯，只要人类未在 GitHub 网页或客户端点击 **Confirm Merge**，受保护的 `main` 分支在正确配置审批策略时减少 AI 擅自合并和污染生产代码。

### 2.5 物理工位环境纯净锚点 (Clean Workspace Anchor)
- DEV 工位和 QA 工位各自拉取独立的 Git Worktree，其代码基线完全以 GitHub 远端推送的确定性 SHA 为锚点。
- QA 独立工位验证的代码，必须是 DEV 已经推送到 GitHub 远端 PR 的确切版本，绝不测试 DEV 电脑上的本地脏暂存，为可复算的第三方验证提供固定版本锚点。

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
- **法定禁令**：严禁修改被测业务代码；严禁在存在 P0 缺陷时签署 PASS；严禁脱离 DEV 卡片出具孤立验收；DEV 与 QA 签名者身份严禁重叠。

### 3.5 ⑤ 项目地图总控 (Truth & Ledger Scribe)
- **法定权力**：维护仓库唯一正式项目地图（`PROJECT-MAP.md`）；根据可信裁决器计算出的正式 PASS 结果提出纯文档 PR。
- **法定禁令**：严禁代下技术或质量结论；严禁在缺乏独立 QA 凭据前登记完工；严禁直接合并自己发起的文档 PR。

### 3.6 ★ 中立协调与可信裁决器 (Coordinator & Trusted Evaluator)
- **属性**：中立、无业务裁决权的状态机执行器与密码学强校验引擎。
- **计算职责**：
  1. 物理检查 DEV 提测 SHA 与 QA 验收 SHA 严格一致（`tested_sha == tested_code_sha`）；
  2. 物理检查 SHA 在 Git 对象库中必须属于 `commit` 类型对象（`git cat-file -t == commit`）；
  3. 物理核对 baseline_sha 是 tested_code_sha 的祖先，且变更文件列表与实际 diff 完全一致；
  4. 物理读取 `manifest.json` 并重新计算 SHA-256 哈希，核对是否与卡片一致；
  5. 检查是否存在未解决的 `findings.p0` 缺陷及非零退出码；
  6. 只有上述所有检查全部无误，才计算输出 `QA_PASSED_AWAITING_OWNER_MERGE` 状态。

---

## 4. 标准交接契约格式 (Standard Hand-off Contracts)

数据与控制信号必须通过公开、受版本控制的结构化卡片传递，严禁依赖不透明的聊天上下文摘要。

### 4.1 DEV 交付卡 (`DEV_HANDOFF`)
由 DEV 工位在完成切片自测后，随 PR 描述或 Issue 提交。契约由 `schemas/dev-handoff.schema.json` 强校验：
```yaml
handoff_version: 1
kind: "DEV_HANDOFF"
task_id: "G2-01-DEV-016"
baseline_sha: "40位十六进制commit-hash"       # 必须为 tested_code_sha 的物理祖先
tested_code_sha: "40位十六进制commit-hash"    # 必须为当前 PR HEAD 的物理提交
author: "dev-agent-or-engineer"              # 签署者标识，严禁与 QA 重叠
pr_url: "https://github.com/owner/repo/pull/12"
scope: "切片实施摘要"
changed_files:
  - "path/to/modified/file.py"               # 必须完全覆盖实际 git diff
dev_checks:
  - command: "pytest tests/unit"
    exit_code: 0
not_run:                                     # 严禁留空；若声明 100% 覆盖需提供 exemption_justification
  - "e2e-browser-matrix"
# not_run 需要显式列出尚未覆盖的边界；不得以自由文本豁免
known_risks:
  - "已知边界缺陷或遗留风险"
state: "DEV_READY_FOR_QA"                    # 枚举: DEV_READY_FOR_QA | DEV_BLOCKED
```

### 4.2 QA 裁决卡 (`QA_RESULT`)
由独立 QA 在真实执行后，于 GitHub PR 的 APPROVED Review 正文签署。普通 Issue 评论不触发受保护的 QA 验证。契约由 `schemas/qa-result.schema.json` 强校验：
```yaml
result_version: 1
kind: "QA_RESULT"
task_id: "G2-01-DEV-016"
tested_sha: "40位十六进制commit-hash"        # 必须与 DEV tested_code_sha 严格一致
runner_sha: "40位十六进制commit-hash"        # QA 执行脚本所在 commit，必须存在
qa_contract_sha: "40位十六进制commit-hash"   # 验收契约文件所在 commit，必须存在
author: "qa-auditor-identity"               # 签署者标识，严禁与 DEV 重叠
profile: "Library"                          # 枚举: Library | API-DB | Full-Stack | Rework
environment: "Ubuntu 22.04 LTS, Python 3.11"
verdict: "PASS"                             # 枚举: PASS | FAIL | BLOCKED | NOT_RUN | INVALID_TEST
evidence_manifest_sha256: "64位十六进制哈希"  # <独立 QA 证据目录>/manifest.json 的物理重算哈希
checks:
  - name: "unit_and_integration"
    command: "pytest tests/"
    exit_code: 0                            # verdict 为 PASS 时所有 checks exit_code 必须为 0
findings:
  p0: []                                    # 若包含 P0 缺陷，verdict 严禁为 PASS
  p1: []
  p2: []
next_action: "REQUEST_OWNER_MERGE_AND_MAP_UPDATE"
```

### 4.3 地图更新卡 (`MAP_UPDATE`)
由地图总控随纯文档 PR 发起。契约由 `validate-handoff-cards.yml` 强校验：
```yaml
kind: "MAP_UPDATE"
task_id: "G2-01-DEV-016"
code_pr_number: 12                          # 已合并的代码 PR 编号
code_merged_sha: "40位十六进制commit-hash"   # 已实际合并入 main 的 commit SHA
scribe: "project-map-scribe"
```

---

## 5. 物理隔离纪律 (Physical Isolation Rules)

1. **工作树物理隔离 (Worktree Isolation)**：  
   DEV 工位与 QA 工位必须工作在相互独立的物理路径（如通过 `git worktree add` 挂载），严禁在同一个目录中交替执行修改。
2. **环境与数据隔离 (Disposable State Isolation)**：  
   自动化测试必须运行在轻量沙箱、独立临时数据库（随机端口）、干净虚拟环境中，测试完毕即刻清理，严禁复用污染。
3. **代码写权限隔离 (Read-Only Code Base for QA)**：  
   QA 工位严禁对被测源码拥有写权限。在 Claude Code 中推荐将 QA 设定为只读型子代理（`Explore` 模式）或通过 PreToolUse Hook 阻断。

---

## 6. 核心质量门禁与反证机制 (Quality Gates & Evidence Discipline)

### 6.1 门禁左移与预检 (`pre-handoff`)
DEV 提测前必须在本地通过四道物理门禁（`packages/fpf_gates/pre_handoff.py`）：
1. **工作树纯净性**：工作树无 untracked 或未暂存脏文件；
2. **治理防线无窜写**：严禁修改 `PROJECT-MAP.md` 与 `LESSONS.md`；
3. **元数据 SHA 祖先有效性**：验证 baseline 是 tested 的真实祖先，且变更文件匹配；
4. **敏感产物审计**：扫描代码与 diff，硬性阻断明文 AWS Key、OpenAI Token、GitHub PAT 及私钥。

### 6.2 变异对抗反证 (Red Check)
- 在任何缺陷修复轮次（Bug-Fix / Rework），强制要求执行 Red Check（变异对抗反证）：
- 将修复后的代码回退至缺陷版本时，该测试用例必须**明确失败**（退出码非 0）。
- 杜绝因测试编写不严谨或断言缺失而产生的“空跑假绿灯”。

### 6.3 错题本制度 (Lessons-Learned Discipline & Seen 3× 晋升)
1. 设立仓库根目录治理文件 `docs/coordination/LESSONS.md`。
2. **录入流程**：DEV 总指挥归纳 $\rightarrow$ QA 总指挥核验事实背书 $\rightarrow$ 人类负责人核准入库。
3. **Seen 3× 自动晋升**：同一类缺陷在 3 个不同切片中复犯，**强制自动晋升为 CI 自动化对抗门禁用例**。
4. **刚性约束**：智能体任务书与 `AGENTS.md` 强制约定：“编码前必须查阅错题本，复犯已知缺陷直接判 DEV FAIL”。

### 6.4 32 项证据包与分级 Profile 契约 (Evidence Pack & Profiles)
详见 [docs/EVIDENCE-SPEC.md](EVIDENCE-SPEC.md)。QA 签署 PASS 必须基于物理证据目录 `<独立 QA 证据目录>/` 中的 `manifest.json`：
- **PROFILE-LIBRARY**：基础代码库，必须覆盖 A、C、D、H 类核心凭据（EVID-01, EVID-04, EVID-09 等）；
- **PROFILE-API-DB**：服务与数据库切片，追加事务凭据与随机端口日志（EVID-02, EVID-05）；
- **PROFILE-FULLSTACK**：全栈切片，追加端到端浏览器渲染与真实接口抓包（EVID-21～24）；
- **PROFILE-REWORK**：返工切片，强制追加红绿变异反证（EVID-25）。
manifest 文件的每一项必须在磁盘上真实存在，且 SHA-256 严丝合缝。

---

## 7. 双 PR 制衡与原子顺序 (Dual-PR Ordering & Anti-Drift Workflow)

为消灭“代码 PR 尚未合并、地图 PR 先行合并导致状态漂移”以及“DEV 在代码 PR 中自改项目地图完工”的重大隐患，协议确立以下流程：

### 7.1 代码 PR 与地图 PR 职能分离 (Separation of Concerns)
- **代码 PR**：仅允许修改功能代码与测试用例，**严禁修改 `PROJECT-MAP.md` 或 `LESSONS.md`**。若检测到混合修改，CI 直接硬阻断并报错退出。
- **地图 PR**：仅允许修改项目地图与错题本等治理文件，必须包含 `MAP_UPDATE` 卡片，且必须锚定一个已经真正合并入主干的代码 commit SHA。

### 7.2 严格合并次序 (Strict Sequential Merging)
1. **第一步（合并代码）**：人类负责人核验 QA PASS 凭证，在 GitHub 上点击 Squash Merge 代码 PR，在主干生成确定的 `MERGE_COMMIT_SHA`；
2. **第二步（提交地图）**：地图总控 Scribe 获取该主干 `MERGE_COMMIT_SHA`，写入地图凭据并提交纯文档地图 PR；
3. **第三步（合并地图）**：CI 门禁自动核验 `code_merged_sha` 确系 `main` 分支的祖先提交后放行，人类负责人点击合并地图 PR。

### 7.3 服务端法定防线 (Server-Side Branch Protection)
- `main` 主干开启 GitHub 分支保护规则：
  - 强制开启 `required_status_checks`（必须通过 `validate` 与 `validate-card`）；
  - 强制开启 `enforce_admins: true`；
  - 必须设置至少一名真实独立审查者，且 `required_approving_review_count >= 1`；仅启用 `require_code_owner_reviews` 且批准数为 0 不构成强制审查；
  - 禁用强制推送（`allow_force_pushes: false`）与分支删除（`allow_deletions: false`）。

### 7.4 人类极简终审 (One-page Sovereign Briefing)
通过负责人代理 Agent，将海量运行日志收敛为“一页纸红绿简报”，向人类呈现：
- 切片 ID 与功能范围；
- 提测 SHA 与 QA 验收 SHA 对齐凭据；
- QA 测试结论、覆盖率与未测试项（`not_run`）；
- 阻断性风险与合并建议。
人类决策者仅需据此签署最终决策，将宝贵的人类注意力集中在关键的商业和架构把关上。
