# 工位契约（STATIONS）

本文件是 FPF 异构协作体系的**人读契约**：谁在什么身份下、能做与不能做什么、裁决如何追溯到授权。

它回答一个此前无解的问题：门禁只校验 GitHub 账号（非作者 + APPROVED + QA_RESULT），因此**一个人只要拥有两个 GitHub 身份，就可以合法走完 DEV→QA→合并全流程**。本文件把"角色分离"从口头约定变成可引用的书面契约。

## 一、分层关系

| 层 | 载体 | 性质 | 变更路径 |
|---|---|---|---|
| 人读契约 | `docs/coordination/STATIONS.md`（本文件） | 说明性，不参与判定 | `POLICY_PR` |
| 强制登记表 | `.fpf/stations.yaml` | 受保护，门禁据此解析工位类型 | `GATE_PR`（随 G2 入库） |

本文件**不产生**任何强制力。强制力只在 `.fpf/stations.yaml` 入库并接入门禁判定后成立；在那之前，角色分离依赖执行者自觉。

## 二、四工位登记

| 工位 | 载体 | 稳定标识 | 产出 | 权限边界 |
|---|---|---|---|---|
| ST-DEV-CMD | ChatGPT 会话 | `chatgpt.com/c/6af43318-3fd0-83e8-922d-bf0681205400` | `WORK_ORDER` | 只规划与签发工单；不写代码、不签 QA 裁决 |
| ST-QA-CMD | ChatGPT 独立会话（无前序上下文） | `chatgpt.com/c/6af438e8-eef4-83e8-bbf6-5f34aaf19bca` | 语义裁决（`verdict` / `merge_now_ok`） | 只裁决语义；不产生 GitHub review、不 dispatch workflow |
| ST-DEV-01 | Codex worker（`luna_worker`） | 线程 ID | 代码/文档提交 | 不得签发自己的 QA 裁决 |
| ST-QA-01 | Codex worker（独立于 DEV-01） | 线程 ID | 反向测试与缺陷报告 | 只审 DEV-01 的产出；不自批 |

补充执行身份（非工位，属凭据载体）：

| 身份 | 载体 | 权限 | 用途 |
|---|---|---|---|
| `fpf-qa-bot-huangzuomin[bot]` | GitHub App | `actions:write` + `pull_requests:write` | dispatch 独立 QA、签发 `QA_RESULT` |
| `fpf-reviewer-huangzuomin[bot]` | GitHub App 5713253 / installation 180902777 | 仅 `metadata:read` + `pull_requests:write` | 承载书面授权，**不产生裁决**、不 dispatch |

## 三、角色分离规则

1. **裁决身份 ≠ 开发身份。** 任何 `QA_RESULT` 的 `author` 必须与 `DEV_HANDOFF.author` 不同，且 QA run 的 `actor` 与 `triggering_actor` 都不得等于 PR 作者。
2. **第二批准 ≠ 第一批准。** GATE_PR 的第二个 APPROVED 必须来自与 QA reviewer 不同的身份。
3. **承载 ≠ 产生。** `reviewer2` 的 APPROVED 只承载负责人代理工单的书面授权，必须在 review body 引用工单编号与授权原文；它不得自行判定 PASS。
4. **解析失败即拒绝。** 门禁无法把某个身份解析到登记工位时，必须 fail-closed 拒绝，不得默认放行。
5. **例外必须一次性。** 任何绕过角色分离的例外都要写明范围、补偿控制、失效条件，并记入 `docs/coordination/lessons.md`。

## 四、历史溯源

本契约此前只存在于 `.fpf-runtime/coordination/`（被 `.gitignore` 忽略，`git ls-files` 计数为 0）。后果是可复现的：新线程、新会话、新 agent 读不到协议，每轮都要重建；协同因此退化为"执行者的自觉"，而非仓库里的制度。

本文件首次为该协议提供可跟踪载体。强制登记表（`.fpf/stations.yaml`）与其门禁接入属 G2 切片，本文件不预先声明其已生效。

## 五、生效状态（G2 已合入，2026-11-12 更新）

- `.fpf/stations.yaml` 已随 PR #85 入库（合并 SHA `2da17a9e2c7a3f0b3b691440ae03c0b9eb471ced`），门禁从 **PR base commit** 读取登记表（`git show {base}:.fpf/stations.yaml`），因此改表者不能即时为自己授权，新关系合并后才生效。
- **已生效的强制点**（`packages/fpf_policy/pr_gate.py`，路由 `CODE_PR` / `GATE_PR`）：
  - R0：登记表缺失或结构非法即 fail-closed；
  - R1：`QA_RESULT` 签发者必须解析到 `kind: qa-evidence`；
  - R2：PR 作者不得解析到 `{qa, qa-evidence, ruling-carrier}` 任一工位；
  - R3：`GATE_PR` 的第二 `APPROVED` 必须解析到 `kind: ruling-carrier`，且与 R1 工位 id 不同；
  - R4：登记表结构校验（id/carrier 非空且唯一、kind 合法、重复键拒绝、`version: 1`）；
  - R5：`sovereign_override` 键**存在即拒**，作者自授权分支已废除。
- **负向证据**：`tests/test_gate_stations.py`（19 用例，含"候选 head 篡改登记表仍按 base 判定"、"`sovereign_override` 四种取值全部拒绝"）；`tests/test_qa_evidence_pipeline.py::test_gate_pr_sovereign_override_is_rejected`。全量 `python -m unittest discover -s tests -p "test_*.py"` = 211 passed。

### 未覆盖范围（有意窄化，如实记录）

- `MAP_PR` / `POLICY_PR` / `BOOTSTRAP_PR` 路由**不**做工位校验。
- 登记表只接受 `github-login` 载体，因此只能登记**具备 GitHub 登录名**的身份。
- `ST-DEV-CMD` / `ST-QA-CMD`（ChatGPT 会话）与 `ST-DEV-01` / `ST-QA-01`（Codex worker）**不在** `.fpf/stations.yaml` 内：它们没有 GitHub 身份载体，门禁无法解析。这四个工位目前仍是**规范意图**，不是强制约束。

## 六、已知缺口（G3 / G4 输入）

1. **指挥官与 worker 工位无机器载体**：新线程能读到工位名，但无法被门禁识别为对应工位；跨会话的"谁签了工单、谁做了裁决"只能靠人工考古 PR 与 `.fpf-runtime/`。
2. **接力账本未持久化**：`WORK_ORDER` / `DEV_HANDOFF` / `QA_RESULT` 的事实散落在 PR body、review body 与未跟踪的 `.fpf-runtime/`，会话重建成本高。
3. **GitHub 原生分支保护未收紧**：`required_approving_review_count` 维持 `0`。实测（探针 PR #86）`fpf-reviewer-huangzuomin[bot]` 在仓库权限模型中是 `permission=none`，其 `APPROVED` **不计入** required review；在单所有者仓库中 `count>=1` 需要第二个具备写权限的非作者身份，属负责人待决项（见 `docs/coordination/project-map.md` 的 `FPF2-GATE-PROBE-20261112`）。
4. **CODEOWNERS 全部自指** `@huangzuomin`：一旦把 `require_code_owner_reviews` 与 `count>=1` 同时启用，将要求作者批准自己的 PR，必然死锁。
