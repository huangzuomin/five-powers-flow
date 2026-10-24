# Five-Powers-Flow Specification (FPF-RFC-001)

> **版本**：v1.0.0 (Formal Standard)  
> **状态**：Active / Production-Proven  
> **分类**：治理与工程协议标准  
> **核心原则**：$\text{DEV 交付} \neq \text{QA 通过} \neq \text{批准合并} \neq \text{批准部署}$

---

## 1. 范围与目标 (Scope & Objective)

本协议旨在规范多智能体（Multi-Agent System）与人类软件工程师协同开发生产级软件系统时的**权力边界、状态迁移契约、环境隔离与审计存证标准**。

本规范适用于任何追求高可靠性、防假阳性、防代码污染与合规审计的自动化软件交付场景。

---

## 2. 治理五权与中立总线规范 (Five Powers & Relay Bus)

```
                            [① 人类最高决策者]
                                   │ 战略授权 / 终审决定
                            [② 负责人代理 Agent]
                                   │ 切片推进 / 异常熔断
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
   [③ DEV 总指挥]             [④ QA 总指挥]            [⑤ 项目地图总控]
   (架构规划权)               (独立监察权)              (事实记账权)
         │                         │                         │
         └──────────────────┬──────┴─────────────────────────┘
                            │
               [★ 协调与指令转发 Agent / 中立总线]
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
        [DEV 独立工位]               [QA 独立工位]
```

### 2.1 ① 人类最高决策者 (Human Sovereign)
- **法定权力**：业务范围授权、代码合并入主干（Merge）、正式部署上线、商业与法务最终决策。
- **法定禁令**：不得由任何 Agent 冒名代签；不得将不可逆的操作权限交由自动化推定。

### 2.2 ② 负责人代理 Agent (Owner's Delegate)
- **法定权力**：在人类既定授权内推进任务序列；监控执行工位的运行与 Token 消耗；检测到异常、死锁或越界时触发熔断保护；生成“双 PR 红绿简报”。
- **法定禁令**：未经人类明示授权，严禁对主干执行 Merge 或部署；严禁替 QA 签署测试结论。

### 2.3 ③ DEV 总指挥 (System Architect)
- **法定权力**：切片范围审计与架构设计；裁剪出最小 Spec；签发标准 DEV 工作令（Work Order）；审核 DEV 工位交付物的完整性。
- **法定禁令**：严禁自写自测后宣称通过独立质检；严禁直接修改正式项目地图；严禁发起主干合并。

### 2.4 ④ QA 总指挥 (Independent Auditor)
- **法定权力**：审核切片提测入场门禁（Admission Gate）；独立设计对抗用例与真实业务消融；核验 32 项原始测试日志与哈希锚点；签发法定裁决（`PASS` / `FAIL` / `BLOCKED` / `INVALID_TEST`）。
- **法定禁令**：严禁修改被测业务代码；严禁使用单纯内存 Mock 掩盖外部真实依赖；严禁为未在物理隔离环境跑通的代码背书。

### 2.5 ⑤ 项目地图总控 (Truth & Ledger Scribe)
- **法定权力**：维护仓库唯一正式项目地图（`PROJECT-MAP.md`）；根据 QA 总指挥签发的正式 PASS 报告提出纯文档 PR。
- **法定禁令**：严禁代下技术或质量结论；严禁在缺乏独立 QA 凭据前登记完工；严禁直接合并自己发起的文档 PR。

### 2.6 ★ 协调与指令转发 Agent (Coordinator & Relay Bus)
- **属性**：中立、无业务裁决权的状态机执行器与事件总线。
- **职责**：
  1. 监听 VCS（GitHub/GitLab）的 Issue、PR、Label 与 Commit 跃迁；
  2. 依据状态机判定下一合法角色，并通过通信适配器（RPC / Playwright / Webhook）送达指令；
  3. 管理执行工位（Git Worktree、临时数据库、独立端口）的物理生命周期；
  4. 遇到通道阻断时，自动降级并输出人类可复制的标准化短指令。

---

## 3. 标准交接契约格式 (Standard Hand-off Contracts)

数据与控制信号必须通过公开、受版本控制的结构化卡片传递，严禁依赖不透明的聊天上下文摘要。

### 3.1 DEV 交付卡 (`DEV_HANDOFF`)
由 DEV 工位在完成切片自测后，随 PR 描述或 Issue 提交：
```yaml
handoff_version: 1
kind: DEV_HANDOFF
task_id: "<切片编号, 如 DEV-001>"
baseline_sha: "<完整40位父提交SHA>"
tested_code_sha: "<完整40位提测代码SHA>" # 绝不能使用浮动的分支名或HEAD指针
pr_url: "<PR完整链接>"
scope: "<切片边界详细说明>"
changed_files:
  - "<修改文件路径1>"
  - "<修改文件路径2>"
dev_checks:
  - command: "<真实执行的测试命令>"
    exit_code: 0
    environment: "<Python/Node版本, OS, 硬件>"
    raw_log_anchor: "sha256:<日志哈希>"
not_run: ["<明确未执行的测试及客观原因>"]
known_risks: ["<已知边界缺陷或遗留风险>"]
state: "DEV_READY_FOR_QA" # 枚举: DEV_READY_FOR_QA | DEV_BLOCKED
```

### 3.2 QA 裁决卡 (`QA_RESULT`)
由 QA 总指挥在独立工位完成回归后签署在 Issue 下：
```yaml
result_version: 1
kind: QA_RESULT
task_id: "<切片编号>"
tested_sha: "<完整40位代码SHA, 必须与DEV一致>"
runner_sha: "<QA测试工具链40位SHA>"
qa_contract_sha: "<验收契约40位SHA>"
environment: "<独立隔离环境, 如 OS, 独立PG端口, Headless Browser>"
verdict: "PASS" # 枚举: PASS | FAIL | BLOCKED | NOT_RUN | INVALID_TEST
checks:
  - name: "真实数据库迁移与0% Mock回归"
    exit_code: 0
  - name: "红绿对抗变异测试 (Red-Check)"
    exit_code: 0
evidence_manifest_sha256: "<32项证据包的主哈希>"
findings:
  p0: []
  p1: []
  p2: ["<轻微改进建议>"]
next_action: "REQUEST_OWNER_MERGE_AND_MAP_UPDATE"
```

---

## 4. 物理隔离纪律 (Physical Isolation Rules)

1. **工作树物理隔离 (Worktree Isolation)**：  
   DEV 工位与 QA 工位必须工作在相互独立的物理路径（如通过 `git worktree add` 挂载），严禁在同一个目录中交替执行修改。
2. **环境与数据隔离 (Ephemeral Test Runtime)**：  
   QA 独立验证必须使用随测随启、测完即弃的独立临时数据库（随机端口）和干净依赖环境，禁止向开发共享库或生产库运行清库或破坏性脚本。
3. **代码写权限隔离 (Read-Only QA)**：  
   QA 工位仅拥有被测分支的代码**只读**权限。QA 发现任何缺陷，一律通过 `FAIL` 裁决与错误日志打回 DEV，严禁“顺手修复”。

---

## 5. 核心质量门禁与机制 (Quality Gates)

### 5.1 门禁左移与预检 (`pre-handoff`)
DEV 提测前必须在本地通过确定性检查脚本：
- 工作树无未受控（untracked）或未暂存脏文件；
- 契约接口与 SDK 生成物强一致；
- 交付元数据中 40 位 SHA 有效性校验；
- 必须如实填写 `not_run`，严禁隐瞒未测项。

### 5.2 变异对抗反证 (Red Check)
- 在任何缺陷修复轮次（Bug-Fix / Rework），强制要求执行 Red Check：
- 将修复后的代码回退至缺陷版本，该测试用例必须**明确失败**（退出码非 0）。
- 杜绝因测试编写不严谨而产生的“空跑绿灯”假象。

### 5.3 错题本制度 (Lessons-Learned Discipline)
1. 设立仓库根目录 `docs/coordination/LESSONS.md`。
2. **录入流程**：DEV 总指挥归纳 $\rightarrow$ QA 总指挥核验事实并背书 $\rightarrow$ 人类负责人核准入库。
3. **Seen 3× 晋升规则**：同一类缺陷在 3 个不同切片中复犯，**强制自动晋升为 CI 自动化对抗门禁用例**。
4. **刚性约束**：智能体任务书与 `AGENTS.md` 强制约定：“编码前必须查阅错题本，复犯已知缺陷直接判 DEV FAIL”。

---

## 6. 双 PR 制衡与极简终审 (Dual-PR Workflow)

1. **代码与事实分离**：
   - DEV 工位发起：**代码 PR**（包含业务与自测代码）；
   - 地图总控发起：**地图 PR**（仅包含纯文档 `PROJECT-MAP.md` 更新）。
2. **杜绝自改试卷**：DEV 代码 PR 严禁私自修改 `PROJECT-MAP.md`。
3. **简报收敛体验**：协调中枢负责聚合双 PR 信息，向人类最高决策者呈现红绿对照的一页纸简报。人类只需：
   - 审查简报结论；
   - 点击两次确认合并（代码 PR + 地图 PR）；
   - 既维护了宪法级分权，又实现了极致顺畅的人机交互。
