# Five-Powers-Flow (FPF) 规范操作指南

---

## 📖 核心理念与五权架构

FPF（五权分立人机协同自治软件工程框架）将权力解耦为五项独立的法定职责，以 GitHub 为唯一法定事实源，以物理工位隔离与密码学 SHA 约束为机械强制手段：

| 治理权力 | 载体推荐 | 核心权责 | 法定红线（严禁越界） |
| :--- | :--- | :--- | :--- |
| **① 最高决策权** (*Sovereign*) | **人类项目负责人** | 战略准入、合并（Merge）、正式发布部署、不可逆法律责任承担。 | 严禁自动化代签；绝不下放最终决断权。 |
| **② 代理行政权** (*Delegate*) | **Codex/Orchestrator** | 推进切片队列、工作区流转、Token 监控、状态机调度。 | 严禁私自修改主干；严禁代签 QA 验收结论。 |
| **③ 架构规划权** (*Architect*) | **ChatGPT/Claude 线程** | 需求审计、规格裁剪、签发 DEV 工作令（Work Order）。 | 严禁自写自测冒充独立质检；严禁篡改正式地图。 |
| **④ 独立监察权** (*Auditor*) | **独立 GitHub App 账号** | 红绿对抗验证、审查 14~32 项物理证据日志、出具法定裁决（PASS/FAIL）。 | 严禁修改被测业务代码；严禁纯 Mock 自嗨。 |
| **⑤ 事实记账权** (*Scribe*) | **项目地图专项线程** | 维护单一事实源 `PROJECT-MAP.md`；核验独立 QA 报告后发起纯文档 PR。 | 严禁代下技术结论；严禁合并自己提起的文档 PR。 |

---

## 🛡️ 准备工作：配置 GitHub 独立审查主体与分支保护

为满足“双主体隔离”要求，必须配置专用的 GitHub App（如 `fpf-qa-bot-huangzuomin`）作为独立质检审查者：

### 1. 配置独立质检 GitHub App
- **权限清单**：
  - `Repository Permissions` -> `Pull requests`: Read & write（用于提交审查评论与批准）；
  - `Repository Permissions` -> `Actions`: Read & write（用于触发与复核工作流）；
  - `Repository Permissions` -> `Contents`: Read & write（用于拉取提交与检出代码）。
- **凭据部署**：
  - 下载 App 的私钥 PEM 文件，存放于 `.fpf-runtime/credentials/fpf-qa-app.pem`；
  - 记录 App ID 与 Installation ID 至 `.fpf-runtime/credentials/fpf-qa-app.json`。

### 2. 配置主干分支保护规则（Branch Protection）
在 GitHub 仓库中，进入 **Settings -> Branches -> Add branch ruleset**，针对 `main`（或 `master`）分支配置：
- **Require status checks to pass**：勾选 `validate` 与 `validate-card`；
- **Require a pull request before merging**：勾选 `Require review from Code Owners`；
- **Do not allow bypassing the above settings**（`enforce_admins: true`）：即便管理员也必须遵循独立质检与 CI 规则。

---

## 🚀 步骤一：新项目初始化与物理工位部署 (Bootstrap)

新项目接入 FPF 时，切勿在主干直接生成文件，必须通过物理隔离的独立工位进行规范化接入。

### 1. 运行只读规划（Plan）
```bash
python -m packages.fpf_bootstrap.cli init \
  --repo "/path/to/target-repo" \
  --workspace-root "/path/to/workspaces" \
  --project-id DEMO01 \
  --title "项目名称" \
  --agent-mode manual
```
- 检查输出的 `discovery` 元数据、规划生成的文件列表与工位路径。

### 2. 应用物理工位部署（Apply）
追加 `--apply` 参数创建独立工作树：
```bash
python -m packages.fpf_bootstrap.cli init \
  --repo "/path/to/target-repo" \
  --workspace-root "/path/to/workspaces" \
  --project-id DEMO01 \
  --title "项目名称" \
  --agent-mode manual \
  --apply
```
将在工作区建立三个完全隔离的物理工作区：
- `bootstrap/`：挂载分支 `fpf/bootstrap-DEMO01`（包含纯治理与门禁模板，绝无业务代码）；
- `dev/`：挂载分支 `fpf/dev-DEMO01`（供后续开发切片使用）；
- `qa/`：游离 HEAD 检出，供质检对抗测试使用。

### 3. 运行安全体检与状态门禁（Doctor）
```bash
python -m packages.fpf_bootstrap.cli doctor \
  --repo "/path/to/target-repo" \
  --workspace-root "/path/to/workspaces" \
  --project-id DEMO01
```
- **机械断言**：在未经人类批准合并主干前，命令必须返回 `BOOTSTRAP_PARTIAL`（退出码 2），明确阻断冒进。

### 4. 提交并提起 BOOTSTRAP_PR
在 `bootstrap/` 目录下提交治理文件并推送，提起 Draft PR，PR 描述必须携带法定 `BOOTSTRAP` 卡片：
```yaml
kind: BOOTSTRAP
project_id: DEMO01
baseline_sha: <目标仓库当前基线SHA>
tested_code_sha: <当前提交SHA>
title: 项目名称
```

---

## 💻 步骤二：切片研发流程 (DEV Workstation)

所有业务开发必须在 `dev/` 工位进行，严禁跨工位窜写。

### 1. 编写业务代码与自测
在 `dev/` 工位编写业务代码与单元测试。  
- **法定红线**：严禁触碰 `AGENTS.md`、`docs/coordination/PROJECT-MAP.md`、`docs/coordination/LESSONS.md` 或 `.github/`。
- 本地自测使用 `-B` 参数避免产生未受控的字节码缓存：`python -B <测试脚本>`。

### 2. 运行提测前机械门禁（Pre-Handoff Quality Gate）
```bash
python packages/fpf_gates/pre_handoff.py --base main
```
门禁通过后提交代码生成确切的 Commit SHA。

---

## 🔍 步骤三：独立质检与红绿对抗 (QA & Red-Green Rework)

质检必须由外部独立工位（`qa/`）与独立上下文 Agent 执行。

### 1. 独立工位检出固定 Commit SHA
```bash
cd qa/
git checkout --detach <DEV提交的SHA>
```

### 2. 红对抗验证（Red Check）与返工触发
- QA 构造异常边界值运行对抗测试。
- 若对抗测试失败，QA 出具 `verdict: FAIL`，状态机记录 `last_failure` 并退回 `NEEDS_REWORK`，触发 DEV 返工。

### 3. 绿验证（Green Check）与物理证据归档
- DEV 修复后提交新 SHA，QA 再次在 `qa/` 工位以游离状态检出新 SHA。
- 重新执行对抗测试，确认退出码为 0，出具 `verdict: PASS`。
- 调用证据收集器产出真实物理证据（14 项命令日志 + 2 项哈希清单）：
```bash
python -m packages.fpf_policy.qa_collector \
  --plan .fpf/qa-plan.json \
  --repo qa/ \
  --out .fpf-external-qa/TASK-001/<SHA> \
  --task-id TASK-001 \
  --tested-sha <SHA> \
  --profile Library
```

---

## ⚖️ 步骤四：双 PR 制衡与合并流转 (Dual PR & Merge)

### 1. 代码 PR（Code PR，由 DEV 提起）
发布 Draft PR，PR 正文嵌入标准 `DEV_HANDOFF` YAML 卡片，精确绑定 `tested_code_sha`。

### 2. 独立 QA 主体签署法定审查
由 `fpf-qa-bot-huangzuomin[bot]` 执行核验并在 GitHub 提交正式 `APPROVED` 审查，正文附带 `QA_RESULT` 卡片与 `evidence_manifest_sha256`。

### 3. 人类负责人终审与主干合并（Squash Merge）
人类负责人核验红绿简报与 CI 绿灯后，在 GitHub 点击 Merge，代码合入主干生成正式提交 SHA。

### 4. 地图 PR（Map PR，由地图总控提起）
事实记账线程提交纯文档 PR，根据 `code_merged_sha` 更新 `PROJECT-MAP.md`。CI 验证祖先关系后由人类合入，切片正式闭环。
