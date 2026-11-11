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

## 五、当前未生效项（如实记录）

- `.fpf/stations.yaml` 尚未入库，门禁**尚未**校验工位身份。
- 因此本文件目前是**规范意图**，不是可执行的强制约束。
- G2 落地后，本节应改写为"已生效"，并附负向测试证据（非登记工位身份发 QA review 必须被拒）。
