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
