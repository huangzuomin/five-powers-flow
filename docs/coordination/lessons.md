# 错题本 (LESSONS.md)

> **说明**：本文件记录项目在演进过程中踩过的硬坑与真实教训。  
> **三权共管**：DEV 总指挥总结起草 → QA 总指挥核验事实背书 → 人类负责人核准生效。  
> **Seen 3× 晋升规则**：任何缺陷在 3 个不同切片中复犯，自动晋升为 CI 自动化对抗测试用例。

## 活跃错题表 (Active Lessons)

### `[LESSON-001]` `.git/info/exclude` 被外部写入防护规则
- **触发源**：PR #67 收口（2026-11-11）
- **缺陷现象**：`2026-11-11 12:54:40 +0800`，`.git/info/exclude` 被外部追加 `.inflow-setup/`、`*.hex`、`secrets/`；未找到归属进程，写入者记为 `UNKNOWN`。
- **事实边界**：写入内容与已提交 `.gitignore`（`a7ac512`）同向，属防护性；主工作区 `git status --porcelain` 由 708 项变为 707 项。未回滚，保留防护。
- **治理红线**：仓库忽略规则必须版本化在 `.gitignore`；`.git/info/exclude` 仅作本机补充，任何外部写入必须记账并尝试溯源，找不到即记 `UNKNOWN`，不得臆断。
- **复犯计数**：1 / 3

### `[LESSON-002]` `git fetch --prune` 删除上游已删远端跟踪引用
- **触发源**：PR #67 收口（2026-11-11）
- **缺陷现象**：`git fetch origin --prune` 删除 `origin/fix/runtime-rework-and-audit-docs`。
- **事实边界**：上游已删除该引用，属正常同步行为；未删除本地分支或 worktree，未影响任何未推送提交。
- **治理红线**：`--prune` 属常规卫生操作；执行前确认无本地工作依赖将被清理的远端跟踪引用。
- **复犯计数**：1 / 3

### `[LESSON-003]` PR body 换行在 PowerShell 文本重定向中被破坏
- **触发源**：PR #67 收口（2026-11-11）
- **缺陷现象**：用 PowerShell 读取并经 `gh pr edit --body-file` 回写 PR #67 body 时，换行丢失，YAML 卡被压成单行，`validate-card` 失败（Run `42969645944`）。
- **修复**：改用 Python 以 UTF-8/LF 重建 body（3834 bytes），`validate-card` 恢复 SUCCESS（Run `42969714418`）。
- **治理红线**：跨 shell 处理多行 Markdown/YAML 必须使用二进制安全写入（Python/Node），不得依赖 PowerShell 文本重定向或 `Set-Content` 的默认编码。
- **复犯计数**：1 / 3

### `[LESSON-004]` 同一 head 上旧失败 check run 会令平台合并态短暂 `BLOCKED`
- **触发源**：PR #67 收口（2026-11-11）
- **缺陷现象**：`validate-card` 旧 Run `42963956010` / `42963971379` 失败、新 Run `42968842447` 成功后，`mergeStateStatus` 仍为 `BLOCKED`；触发一次无害的 PR body 刷新后变为 `CLEAN`。
- **事实边界**：对比已合并 PR #75（同样存在旧 failure + 新 success）证明旧失败 run 不必然阻止合并；本次为平台聚合/缓存现象，非门禁代码缺陷。
- **治理红线**：门禁转绿后、合并前必须复核 `mergeStateStatus`；若为 `BLOCKED` 且最新 required check 为 SUCCESS，先触发无害 PR 事件刷新并复测，不得直接改门禁代码或强行合并。
- **复犯计数**：1 / 3

### `[LESSON-005]` 独立 QA 身份可能已存在，勿因“协作者仅 1 人”误判为硬阻塞
- **触发源**：PR #67 收口（2026-11-11）
- **缺陷现象**：工单假设 repo secrets=0、协作者仅 `huangzuomin` 即“无独立 QA reviewer 身份”；实测本机已有 GitHub App `fpf-qa-bot-huangzuomin`（installation `175062735`），权限恰为 `actions:write` / `pull_requests:write` / `contents:read`，并已真实完成 QA dispatch、artifact 取证与 APPROVED review。
- **治理红线**：判定身份或工具链缺失前必须全景探测（GitHub App installation、凭据代理、历史 Review 主体）；协作者列表不是唯一事实源。探测到的既有凭据只在工单授权范围内使用，且必须真实执行 QA，不得本地伪造裁决。
- **复犯计数**：1 / 3

### `[LESSON-006]` 新 profile / 新证据编号必须同时改 schema，否则门禁拒绝自己的产物
- **触发源**：PR #79 收口（2026-11-12）
- **缺陷现象**：PR #80 引入了 `DOC` profile 与 `EVID-33/34`，但漏改 `schemas/qa-result.schema.json`、`schemas/manifest.schema.json` 的 `profile` 枚举与 `id` 正则（写死到 `EVID-32`）。后果是 DOC 卡与 DOC artifact 在 `validate-card` 被 jsonschema 拒绝，需要两次额外的 GATE_PR（#81、#82）才能补齐。
- **根因**：`coordinator.REQUIRED_PROFILE_EVIDENCES` 与 `.fpf/qa-plan.json` 是"运行时事实"，两个 JSON Schema 是"契约事实"，两者没有一致性测试。
- **治理红线**：新增 profile 或新增 EVID 编号时，必须同时更新 `.fpf/qa-plan.json`、`coordinator`、workflow 选项、`schemas/*.json`，并补一条"产物能通过自身 schema"的测试；只改其中三处等于没改。
- **复犯计数**：1 / 3

### `[LESSON-007]` required check 取"最新一次"结论；重跑旧 run 会重放旧事件载荷
- **触发源**：PR #80 / #81 / #82 / #83 收口（2026-11-12）
- **缺陷现象**：同一 head 上 `validate-card` 既有 failure 又有 success 时，`mergeStateStatus` 可能仍为 `BLOCKED`，且 REST 合并接口报 `Required status check "validate-card" is failing`。实测规律：平台取该 context **最新一次** completed run 的结论；若最新一次是 failure 则阻塞。
- **关键细节**：`gh run rerun --failed` 会**重放原始事件载荷**（含当时的 PR body）。因此只有在 body 自那次 run 之后**未变**时，重跑才会转绿；body 变过就必须触发新的 `pull_request_review` 事件产生更新的 success。
- **治理红线**：门禁转绿后合并前，先按 `started_at` 排序核对"最新一次 required check"；`BLOCKED` 时优先触发无害的新事件（重发 review / 刷新 body），不要改门禁代码，也不要用 `--admin` 绕过 `enforce_admins`。
- **复犯计数**：1 / 3（与 `LESSON-004` 同一现象，本条补充了"最新一次"与"重放旧载荷"两条实测规律）

### `[LESSON-008]` 判定"是否已被 .gitignore 覆盖"必须查 origin/main，不能查本地旧检出
- **触发源**：协同机制诊断（2026-11-12）
- **缺陷现象**：以 `git check-ignore -v` 的输出断言"`.inflow-setup/` 的主防线仍在 `.git/info/exclude`、未入库"，属于误读。本地主工作区停在 `b085d44`（旧检出，按零触碰约定不更新），其 `.gitignore` 尚无该规则；`origin/main` 的 `.gitignore:39-42` 早已包含 `.inflow-setup/`、`secrets/`、`*.hex`（PR #67 `a7ac512` 入库）。
- **根因**：`check-ignore` 只报告命中的那一条规则，不报告"更高优先级文件里是否也有"；本地检出落后时，结论会指向 `.git/info/exclude`。
- **治理红线**：任何"某规则是否已入库"的判定，一律以 `git show origin/main:<path>` 或 GitHub Contents API 为准；本地工作区只用于判定"本机当前状态"。
- **复犯计数**：1 / 3

### `[LESSON-009]` 一次性例外可以"未被行使即作废"，但必须书面记录全过程
- **触发源**：`FPF2-STD-SPEC-01` 收口（2026-11-12）
- **经过**：QA 总指挥结构性否决 Library profile 后，负责人代理裁定采纳"方案 B（一次性例外）"。在例外被行使之前，DOC profile 先落地并合并，独立 QA 得以真实执行 `EVID-33/34`；第六轮裁决给出 `verdict: PASS`，并明确 `exception_status: 作废`。
- **治理红线**：例外一旦签发就进入台账，无论是否被使用；作废必须由原裁决方书面确认，并记录"提出 → 否决 → 替代方案落地 → 作废"的完整链路。例外不得被后续切片引用。
- **复犯计数**：1 / 3

### `[LESSON-010]` GitHub 原生 required review 不统计 App 安装身份的批准
- **触发源**：G2 收口分支保护探针（2026-11-12，PR #86）
- **缺陷现象**：`fpf-reviewer-huangzuomin[bot]` 对 head 提交了 `APPROVED`（review 在时间线可见、`validate-card` 认可），但把分支保护改成 `required_approving_review_count=1` 后 `mergeStateStatus` 变为 `BLOCKED`、`reviewDecision=REVIEW_REQUIRED`。
- **根因**：`GET /repos/{owner}/{repo}/collaborators/fpf-reviewer-huangzuomin[bot]/permission` 返回 `{"permission":"none"}`，review 的 `authorAssociation=NONE`。GitHub 原生 required review 只统计**具备仓库写权限**身份的批准；App 安装权限（`pull_requests: write`）不等于仓库角色。
- **治理红线**：任何"平台层强制批准"的设计，必须先实测批准主体在仓库权限模型中的角色；不得由 `validate-card` 通过就推断分支保护也会通过。收紧不可达时必须立即回滚，禁止留下不可合并状态。
- **复犯计数**：1 / 3

### `[LESSON-011]` 同名 check run 新旧并存时 rollup 仍为 FAILURE，须重跑旧 run
- **触发源**：G2 收口探针（2026-11-12，PR #86）
- **缺陷现象**：同一 head `84a5c0b9` 上，`validate-card` 先 failure（Run `43059903481`）、后由 `pull_request_review` 事件产生 success（Run `43060211875`），但 `commits.statusCheckRollup.state` 仍为 `FAILURE`、`mergeStateStatus=BLOCKED`。
- **关键细节**：`gh run rerun <old-id> --failed` 会重放**旧事件载荷**，但门禁判定是**实时查 GitHub API**（review、artifact），因此旧 run 重跑后读到已存在的批准而转绿；rollup 随之清空失败项。这一点修正了 `LESSON-007` 中"body 变过则重跑必失败"的绝对化表述——是否转绿取决于门禁读的是事件快照还是实时状态。
- **治理红线**：合并前必须同时检查"最新一次 required check"与 `statusCheckRollup.state`；存在历史失败项时优先重跑旧 run，其次触发新事件，最后才考虑改门禁代码（默认禁止）。
- **复犯计数**：1 / 3

### `[LESSON-012]` 协议只有"载体"不够，还必须能被门禁解析，否则机制不成立
- **触发源**：协同机制诊断 + G2 落地（2026-11-12）
- **缺陷现象**：工位协议早期只存在于 `.fpf-runtime/coordination/`（`.gitignore` 忽略、`git ls-files` 计数 0），新线程读不到，协同退化为执行者自觉；PR #83 入文档后仍不产生强制力，因为门禁无法把"ChatGPT 会话 ID"或"Codex 线程 ID"解析成工位。
- **根因**：强制力 = 载体（可跟踪文件）+ 解析器（门禁可判定）+ 负向测试。三者缺一，机制都只停留在声明。
- **治理红线**：声称"某协同机制已生效"前，必须能指出①载体路径 ②门禁解析代码位置 ③至少一条负向用例。缺任一项只能表述为"规范意图"或 `PLAN_ONLY`。
- **复犯计数**：1 / 3

### `[LESSON-013]` 基于 `git ls-files` 的扫描必须先 `git add`，否则新文件等于没扫
- **触发源**：G3 切片（2026-11-12，PR #89 首次推送）
- **缺陷现象**：本地 `scan_secrets.py --tracked` 报 0 命中、全量 224 测试全绿；CI 的 `secret-scan` 与 `validate` 同时失败——命中的是 `packages/fpf_gates/secret_scan.py` 自己的 OPENSSH 私钥规则定义行。
- **根因**：扫描器与测试都遍历 `git ls-files`，而本地验证跑在 `git add` **之前**，新文件尚未被跟踪，因此既没被扫描也没被测试覆盖。CI 检出后文件已跟踪，问题立刻暴露。
- **治理红线**：凡是"扫描/统计已跟踪文件"的校验，本地验证必须放在 `git add` 之后；否则本地绿灯只证明"旧文件干净"。同时在实现侧给自己也加抑制标记，避免扫描器把规则定义当成密钥。
- **复犯计数**：1 / 3

### `[LESSON-014]` `tools/` 与 `.githooks/` 在门禁路由里不可达，会与 `.github/` 形成死锁
- **触发源**：G3 切片（2026-11-12，PR #89 第二次推送）
- **缺陷现象**：同一 PR 同时含 `.github/workflows/secret-scan.yml`、`tools/security/*`、`.githooks/pre-commit`。用 `POLICY_CHANGE` 报 `POLICY_CHANGE contains unrelated application files`；改用 `DEV_HANDOFF` 报 `CODE_PR modifies protected governance paths`——两种卡都出不去。
- **根因**：`pr_gate._policy_scope` 只接受受保护前缀、`docs/`、`tests/`、`templates/` 与少数根文件；`packages/` 属受保护前缀而 `tools/` 不在任何一类。于是"受保护路径 + tools"的 PR 既不能走 `GATE_PR` 也不能走 `CODE_PR`。
- **治理红线**：新增仓库级工具前先确认落点可路由——涉及 `.github/` 或 `packages/` 时，工具应放进受保护前缀（本次落在 `packages/fpf_gates/`），或拆分 PR 使每个 PR 的所有路径落在同一类。路由能力本身是治理约束，不只是目录偏好。
- **复犯计数**：1 / 3

### `[LESSON-015]` 工单里的"先例事实"必须实测复核，不能直接写进宪制文本
- **触发源**：G2 C4 裁定（2026-11-12，PR #90）
- **缺陷现象**：工单证据条款称"PR #67/#78 零 review 合并先例"。API 实测 #67 有 5 条 review、#78 有 1 条，前提不成立。
- **根因**：把"review 主体不具仓库写权限、对原生计数无效"与"没有 review"混为一谈。
- **治理红线**：写入路线图/宪制文本的每条先例都必须能追溯到一次 API 或仓库实测；发现前提错误时按"纠正后表述"落笔并在 PR 正文如实标注偏差，而不是照抄错误前提或默默改写。
- **复犯计数**：1 / 3

### `[LESSON-016]` 被审查者不得定义本次审查的标准（否则抬高即死锁、降低即自放水）
- **触发源**：G4 B03 修复（2026-11-12，PR #100/#101）
- **缺陷现象**：`validate-card` 只把 `packages/fpf_policy/` 从 base 恢复，而强制证据表 `REQUIRED_PROFILE_EVIDENCES` 在 `packages/fpf_coordinator/coordinator.py`，由 **PR head** 决定。PR #100 把 Library 从 16 项抬到 18 项后，用其唯一真实 artifact（main 采集器只能产 16 项）跑真实门禁被判 `omitted mandatory evidence items: ['EVID-35','EVID-36']` —— 变更不可门禁；反向则任何 PR 都能缩小 `_LIB` 降低自己的门槛。
- **根因**：门禁的"要求"与"被要求对象"没有分离，同一条 base 锚定只做了一半。
- **治理红线**：①门禁的一切判定输入（校验逻辑 + 要求表）必须来自 base/可信侧；②**强制证据项变更必须分两步**：先落 plan/命令（可在旧表下门禁），再落强制集（此时 base 已能产出该项）；③凡声称"要求已收紧"，必须给出 head 缩表被拒、head 扩表不对本 PR 生效的负向用例。
- **复犯计数**：1 / 3

### `[LESSON-017]` 同一语义的两份实现：修好一份不能证明另一份
- **触发源**：G4 FINAL-R3 裁决（2026-11-12，B01）
- **缺陷现象**：`github_source._pages()` 已改为"遇非 dict 抛错"，但实际采集入口 `fact_source._page()` 仍是 `[item for item in data if isinstance(item, dict)]` —— **过滤**而非拒绝。100 条里丢 1 条会被读成"最后一页"，采集提前结束且页摘要按过滤后集合计算，缺陷被"干净"的结果掩盖。
- **根因**：以"同名逻辑的另一份实现已修"代替"实际执行路径已修"。
- **治理红线**：修缺陷前先用调用链确认**实际入口**（`grep` 调用点，不看同名函数）；"过滤"与"拒绝"在证据链里不等价，凡是影响分页/摘要/计数的集合处理，一律 fail-closed 拒绝，禁止静默丢弃。
- **复犯计数**：1 / 3

### `[LESSON-018]` 比较必须锚定独立事实源，候选与自身归约比较是自证
- **触发源**：G4 FINAL-R3 裁决（2026-11-12，B02）
- **缺陷现象**：`run_gate` 调用 `compare_event_sequence(replay["ordered_ids"], 候选自身顺序)`，而 `replay` 本身就是由候选事件归约得到。`A→A→B` 与 `A→B→B` 在集合比较下相同、在自证比较下也相同，重复次数缺陷完全漏检。
- **根因**：把"归约器确定性"误当作"候选与可信观测一致"。
- **治理红线**：一致性断言的两侧必须来自**不同来源**（可信采集 vs 候选工件）；多重性（Counter）应先于位置判定，使 `EVENT_DUPLICATE_MISMATCH` 与 `EVENT_ORDER_MISMATCH` 语义可区分；新增比较逻辑必须同时给出"同集合不同多重性"与"同集合逆序"两条反向用例。
- **复犯计数**：1 / 3

### `[LESSON-019]` 摘要对象不可混用：ZIP digest ≠ manifest sha256；稳定观测 ≠ 原子快照
- **触发源**：G4 多轮裁决（2026-11-12）
- **缺陷现象**：申报材料里把平台返回的 artifact **ZIP** digest（如 `66b360eb…`）与本地按字节重算的 `manifest.json` sha256（如 `4ebbd8cf…`）当作同一校验对象引用，二者长度相同、格式相同，极易被误读为"互相印证"。
- **根因**：同一 artifact 上存在多个哈希层级（传输包 / 清单 / 单文件），缺少命名约束。
- **治理红线**：引用哈希必须带对象名（`zip_sha256` / `manifest_sha256` / `file sha256`）；跨层比较一律视为无效证据；对外表述只允许"稳定观测"（`stable_observation: true` / `atomic_snapshot_claimed: false`），GitHub 无跨端点事务，不得声称原子快照。
- **复犯计数**：1 / 3

### `[LESSON-020]` 过宽的本地钩子会把合法路径推向 `--no-verify`，反而降低总防护
- **触发源**：治理收尾（2026-11-12，PR #102 实测）
- **缺陷现象**：`.git/hooks/pre-push` 阻断任何触及 `PROJECT-MAP.md` / `LESSONS.md` 的推送，且无 Scribe 例外。地图记账 PR 必然触及这两个文件，于是每次合法记账都要 `--no-verify` —— 而 `--no-verify` 会关闭该次推送的**全部**钩子检查。
- **根因**：把"角色分离"实现成"路径一刀切"，没有为被授权的角色留显式通道；钩子本身又自述可被 `--no-verify` 绕过，属于"挡君子不挡小人"的控制。
- **治理红线**：客户端钩子只能作为**提示层**，真正的强制必须落在服务端（required checks / `validate-card`）；任何"全量阻断 + 无豁免"的本地检查，都必须同时给出被授权角色的显式放行规则，否则等于制造绕过动机。使用 `--no-verify` 必须附理由并留证。
- **复犯计数**：1 / 3

### `[LESSON-021]` 受保护路径必须在主干上真实存在，否则是"保护空位"
- **触发源**：治理收尾（2026-11-12，AGENTS.md 入库）
- **缺陷现象**：`packages/fpf_policy/protected.py` 的 `EXACT` 集合与 `.github/CODEOWNERS` 都把 `AGENTS.md` 当受保护文件，但该文件**从未进入 origin/main**（只在本地 main 的未推送提交与工作区里）。门禁与 CODEOWNERS 保护的是一个主干上不存在的路径。
- **根因**：本地工作区文件被默认当作仓库事实；`is_protected()` 只做字符串匹配，不校验路径是否存在。
- **治理红线**：宣称"某文件受治理保护"前，必须用 `git ls-tree origin/main <path>` 证明它在主干存在；`CODEOWNERS` 条目同理（大小写敏感平台会静默失效）。本地专用文件若要成为治理对象，先入库再谈保护。
- **复犯计数**：1 / 3
