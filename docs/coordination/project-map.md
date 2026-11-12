# 项目唯一事实地图 (PROJECT-MAP.md)

> **权威性声明**：本文件是本工程唯一权威项目进展地图。  
> 仅允许由项目地图总控（Scribe）角色在核验独立 QA 的 `PASS` 裁决及真实测试证据后，通过独立纯文档 PR 提议更新，并由人类最高决策者审批合入。

## 一、当前里程碑总览

| 切片编号 | 模块 / 目标 | 负责人 | DEV 状态 | 独立 QA 裁决 | 主干合并状态 | 部署状态 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **FPF-AEC-20261031-A** | 架构契约与分阶段规划 | DEV-Lead | DONE (`0fef95e155b3`) | PASS | MERGED (`2327ac1f3641`, PR #69) | DEPLOYED |
| **FPF-AEC-20261031-B** | 协调内核与 24 状态机 | DEV-Team | DONE (`84794e26416c`) | PASS (Run 41205180878) | MERGED (`ad7e904ad33f`, PR #70) | DEPLOYED |
| **FPF-AEC-20261031-C** | 真实 Provider 适配器 | DEV-Team | DONE (`2c5241132dfe`) | PASS (Run 41218539037) | MERGED (`96b38d0f5765`, PR #71) | DEPLOYED |
| **FPF-AEC-20261031-D** | 独立 QA 证据闭环 | DEV-Team | DONE (`00fe28185b21`) | PASS (Run 41219858672) | MERGED (`437d6dd24fd6`, PR #72) | DEPLOYED |
| **FPF-AEC-20261031-E** | 安全防护与环境隔离 | DEV-Team | DONE (`cb9b4372ac1f`) | PASS (Run 41221914610) | MERGED (`15e0c1772248`, PR #73) | DEPLOYED |
| **FPF-AEC-20261031-F** | 持续守护进程与恢复 | DEV-Team | DONE (`8d4e8e7969d8`) | PASS (Run 41223289293) | MERGED (`2ef69643efd4`, PR #74) | DEPLOYED |
| **FPF-AEC-20261031-G** | 终审大考与交付收口 | DEV-Team | DONE (`ac4febdd355b`) | PASS (Run 41225694824) | MERGED (`bac0088055d8`, PR #75) | DEPLOYED |
| **FPF-2.0-ROADMAP-20261031** | FPF 2.0 路线图归并与 G2–H4 复盘新增项 | Orchestration Hub | DONE (`81289d4f5ffe`) | PASS (Run 42968508888) | MERGED (`09d4c6076295`, PR #67) | N/A (docs only) |
| **FPF2-G4-REDUCER-01** | G4 事件驱动状态归约（PROJECTION_ONLY） | Orchestration Hub | DONE (`2aec8763b2d8`) | PASS (FINAL-R4, Run 43183534549) | MERGED (`feaafd3701cb`, PR #92) | N/A (无部署) |
| **FPF2-GATE-ANCHOR-01** | 门禁证据要求表锚定 base（治理收紧） | Orchestration Hub | DONE (`de893a4e2730`) | PASS (Run 43180174197) | MERGED (`19ca7dc1cad2`, PR #101) | N/A |

## 二、切片详细进度记录

### [FPF-AEC-20261031-A] 架构契约与分阶段规划
- **目标**：确立 FPF Autonomous Engineering Coordinator 架构规范与 24 状态机契约
- **代码提交**：`0fef95e155b386d6c27dc63dc5fb74d64326e5e8`
- **主干合并**：`2327ac1f36412fb26c17d291b719930967091200` (PR #69)
- **交付产物**：`docs/architecture/FPF-AUTONOMOUS-ENGINEERING-COORDINATOR.md`
- **归档时间**：2026-10-31

### [FPF-AEC-20261031-B] 协调内核与 24 状态机
- **目标**：实现确定性 24 状态归约器、CAS 乐观锁迁移引擎与 SQLite Journal 数据层
- **代码提交**：`84794e26416c0ee1f7349dc8dfc3aca151c53170`
- **主干合并**：`ad7e904ad33f6bc5eac42cc3fbc2ac46ffd4d771` (PR #70)
- **QA 验收报告**：Run #41205180878 / Artifact `13043482948` (SHA-256: `70b1940f256644cd06c78c42381b5a7987b19ebb467b5b84fea5022055dff40c`)
- **归档时间**：2026-10-31

### [FPF-AEC-20261031-C] 真实 Provider 适配器
- **目标**：实现 ChatGPTWebAdapter（基于 Clean Session 浏览器驱动）与 CodexWorkerAdapter（基于隔离 Worktree）
- **代码提交**：`2c5241132dfe9120a2437f554676aed81bcea29e`
- **主干合并**：`96b38d0f5765c26455382c78759c7f4e12ab4985` (PR #71)
- **QA 验收报告**：Run #41218539037 / Artifact `13049091359` (SHA-256: `587b056490dc969a6e01f3ef7e1b1c02c2d7431aeb08466ec0afa8e223d445f8`)
- **归档时间**：2026-10-31

### [FPF-AEC-20261031-D] 独立 QA 证据闭环
- **目标**：实现独立 QA Artifact 直传解耦存储、密码学校验与双 Reviewer 独立身份审查
- **代码提交**：`00fe28185b213afbd80cfb2db47ff41ab9cbff7c`
- **主干合并**：`437d6dd24fd62b3460aa97a3db926c0502a3b936` (PR #72)
- **QA 验收报告**：Run #41219858672 / Artifact `13049696654` (SHA-256: `0ace5e1e9d1ef5ef5623c83c763394f66c2b55cf467227fc8c09e1e6e99f2957`)
- **归档时间**：2026-10-31

### [FPF-AEC-20261031-E] 安全防护与环境隔离
- **目标**：实现 CredentialBroker 凭据中介、环境变量脱敏、NTFS 只读写保护与 WFP 网络拦截抽象
- **代码提交**：`cb9b4372ac1f5b06dc0cc9b245ba50122d912f20`
- **主干合并**：`15e0c17722487fcf680dc24658928e3b57335b73` (PR #73)
- **QA 验收报告**：Run #41221914610 / Artifact `13050720734` (SHA-256: `e314ebbfe3c05637d4464fea78103b8eaf62be4086f6feb27a38d2b22df0eba6`)
- **归档时间**：2026-11-01

### [FPF-AEC-20261031-F] 持续守护进程与恢复
- **目标**：实现后台常驻 DaemonServer、Heartbeat 补偿调度与未决状态熔断（BLOCKED_RECONCILIATION）
- **代码提交**：`8d4e8e7969d86dab9a303d0e67f06e994018b062`
- **主干合并**：`2ef69643efd429d8e886a988c3f576151ca4b7dd` (PR #74)
- **QA 验收报告**：Run #41223289293 / Artifact `13050891999` (SHA-256: `2d14ba36b74aa13f12ada8936d3ef57675378b99deaac15f6c7c9d02414798ab`)
- **归档时间**：2026-11-01

### [FPF-AEC-20261031-G] 终审大考与自主工程协调完整交付闭环
- **目标**：完成全系统端到端真实切片演练（Golden Path A/B E2E）与权威交付总结报告
- **代码提交**：`ac4febdd355b6ee7ca5e7f54621502bac97de799`
- **主干合并**：`bac0088055d8306843b4e836172cc6246d1d03a6` (PR #75)
- **QA 验收报告**：Run #41225694824 / Artifact `13051708070` (SHA-256: `a29b25ee8d6c6919c24d7580c27c2977e684156340f9b6e4ed413c04848f0046`)
- **归档时间**：2026-11-01

### [FPF-2.0-ROADMAP-20261031] FPF 2.0 标准化路线图归并与 G2–H4 复盘新增项
- **目标**：将 2026-11-10 复盘出的 G2/G3/G4/H1/H2/H3/H4 七项并入 FPF 2.0 路线图，刷新 §2 基线至 2026-11-11，新增「AEC Phase A–G → 六平面」附录，并把 AEC 文档降级为历史阶段快照
- **代码提交**：`81289d4f5ffe6d6db443c8260c7525e0a18adb56`
- **主干合并**：`09d4c60762953503a8baff610f71225cf7ed35f1` (PR #67)
- **QA 验收报告**：Run #42968508888 / Artifact `13832222368` (SHA-256: `24fd52fdc08dcb27a009e744c0432d6177efc1db8dd1c2510fd68a8c88d0f463`)
- **QA 主体**：`fpf-qa-bot-huangzuomin[bot]`；Run `42968508888` 的 `actor` 与 `triggering_actor` 均为该 bot，profile=`Library`，16 项 EVID 全 PASS
- **独立 Review**：`5854472383`，`APPROVED`，`commit_id=81289d4f5ffe6d6db443c8260c7525e0a18adb56`
- **变更范围**：
  - `.gitignore`：新增 `.inflow-setup/`、`secrets/`、`*.hex`
  - `docs/architecture/FPF-AUTONOMOUS-ENGINEERING-COORDINATOR.md`：仅顶部新增 5 行历史快照横幅，正文零改写
  - `docs/roadmap/FPF-2.0-STANDARDIZATION-ROADMAP.md`：1351 行，含 §8.7 G2–H4 与附录 A 映射
- **NOT_RUN / 边界**：
  - G2–H4 七项全部 `PLAN_ONLY`，未实现、未生效、未实机验证
  - 生产部署与真实计费维持 `NOT_AUTHORIZED`
  - 本切片为纯文档变更，无部署动作
- **归档时间**：2026-11-11

### [FPF2-GOV-DOC-PROFILE-20261112] DOC 证据档 + 规范文本路由封堵 + FPF 2.0 标准文本收口
- **目标**：让"纯文档切片"拥有真实可执行的独立 QA 证据，并封堵 `docs/standards/` 走 identity-only 路由的绕过面；随后以 DOC profile 收口 `FPF2-STD-SPEC-01`
- **主干合并（4 个 PR，按序）**：
  - `baf6cf6f6c605a76f6cd228ffd8f23375f73a55c`（PR #80）DOC profile + `promote_doc_route` + DOC 绑定
  - `0687cad6bb9587d1bded46439920146d2435d217`（PR #81）`qa-result` / `manifest` schema 的 `profile` 枚举接受 `DOC`
  - `ac96c2083bcd8b7f698f9892ecec2fbdec2e0d88`（PR #82）manifest `id` 正则放宽到 `EVID-34`
  - `fe627db07a0aa1039ec700a16ec8bb54ab3ba9c7`（PR #79）`docs/standards/FPF-STANDARD-2.0.md` 424 行 + `tools/standards/` 4 文件 + `tests/standards/test_standard_2_0.py`
- **QA 证据（DOC profile，独立执行校验器与测试）**：Run `43052955066` / Artifact `fpf-qa-52ab3f5c3bf020ff2b2c00eef2a681c91d803489`（SHA-256: `fcb69c1b5a201958618b3addcac0eaf8ad353ee229c114ebf9adf74574438937`），18 项全 PASS，含 `EVID-33`（`verify_standard.py`，12/12 检查 PASS）与 `EVID-34`（`pytest tests/standards/test_standard_2_0.py`，3 passed）的原始 stdout/stderr/退出码，均绑定 `tested_sha=52ab3f5c`
- **独立 Review**：`5861538338`，`APPROVED`，`commit_id=52ab3f5c3bf020ff2b2c00eef2a681c91d803489`，主体 `fpf-qa-bot-huangzuomin[bot]`
- **语义裁决**：ST-QA-CMD（`chatgpt.com/c/6af438e8`）第六轮 `verdict: PASS`，`p0_closed: true`，并确认一次性例外（B 方案）**未行使即作废**
- **变更范围**：`.fpf/qa-plan.json` 增 `EVID-33/34`；`packages/fpf_coordinator/coordinator.py` 增 DOC 档与 DOC 绑定（目录即契约、路径同源规范化、无仓库上下文 fail-closed）；`packages/fpf_policy/pr_gate.py` 增 `promote_doc_route` / `touched_paths`；两个 schema 放宽；`tests/test_gate_doc_profile.py` 12 用例（`unittest` 编写）
- **NOT_RUN / 边界**：
  - G2–H4 仍为 `PLAN_ONLY`
  - 生产部署与真实计费 `NOT_AUTHORIZED`
  - `EVID-33/34` 只在 CI 的 `Library`+`DOC` 两条路径上实跑过；浏览器 / 数据库 / 外部 Provider 与本切片无关，`NOT_RUN`
- **归档时间**：2026-11-12

### [FPF2-STATIONS-20261112] 工位契约入库（人读层）
- **目标**：把此前只存在于 `.fpf-runtime/`（未跟踪）的工位协议提升为仓库内可跟踪文件，使新线程可读到角色分离契约
- **代码提交**：`bc521505d2ac80594d8091d2571b08804f3f00d3`
- **主干合并**：`493a15ea963e597b791b2315076fd66ae1ef8929`（PR #83）
- **独立 Review**：`5861627163`，`APPROVED`，`commit_id=bc521505d2ac80594d8091d2571b08804f3f00d3`，主体 `fpf-reviewer-huangzuomin[bot]`（identity-only 路由，无 QA dispatch）
- **变更范围**：新增 `docs/coordination/STATIONS.md`（四工位登记、两个凭据载体权限边界、五条角色分离规则、历史溯源、当前未生效项）
- **NOT_RUN / 边界**：
  - 本文件**不产生强制力**；`.fpf/stations.yaml` 与门禁侧的工位身份校验属 G2，尚未实现
  - 生产部署与真实计费 `NOT_AUTHORIZED`
- **归档时间**：2026-11-12

### [FPF2-G2-20261112] 宪制强制力：工位登记表 + 门禁工位校验 + 废除作者自授权
- **目标**：把"角色分离"从口头约定变成门禁可判定的强制登记表；废除 GATE_PR 的纯自授权旁路
- **代码提交**：`2b8f61c1fbcfdf3dca8292c1d2a10b06d0063c54`
- **主干合并**：`2da17a9e2c7a3f0b3b691440ae03c0b9eb471ced`（PR #85，merge commit）
- **独立 QA**：Run `43059249170` / Artifact `13873495995` / `evidence_manifest_sha256=a82a950cff7501a0caea5089f996db187df9f8736e15ba08a9398efaca276513`，`task_id=FPF2-G2`，`tested_sha=2b8f61c1`，`runner_sha`=`qa_contract_sha`=`835458b5`，`verdict=PASS`
- **独立 Review**：`5862053192`（`fpf-qa-bot-huangzuomin[bot]`，APPROVED，钉 `2b8f61c1`）+ `5862054879`（`fpf-reviewer-huangzuomin[bot]`，APPROVED，钉同一 head，承载 `WO-20261112-mechanize-stations-g2` 授权）
- **变更范围**：新增 `.fpf/stations.yaml`（3 个机器工位）与 `packages/fpf_policy/stations.py`；`pr_gate.py` 增加 R0–R5 并**删除 `sovereign_override` 分支**；`tests/test_gate_stations.py` 19 用例；两个既有测试改造
- **强制规则**：R0 登记表取自 `git show {base}:.fpf/stations.yaml`（不读候选 head，改表者不能即时自我授权）；R1 QA_RESULT 签发者须为 `qa-evidence` 工位；R2 作者不得属 `{qa, qa-evidence, ruling-carrier}`；R3 GATE_PR 第二批准须为 `ruling-carrier` 且与 R1 工位不同；R5 `sovereign_override` 键存在即拒
- **本地验证**：`python -m unittest discover -s tests -p "test_*.py"` = **211 passed**
- **NOT_RUN / 边界**：
  - 工位校验只作用于 `CODE_PR` / `GATE_PR`；`MAP_PR` / `POLICY_PR` / `BOOTSTRAP_PR` 有意不扩围
  - `required_approving_review_count` 仍为 `0`，见下条探针结论；roadmap §8.7.2 的 G2 整体验收**未闭合**
  - `.fpf/stations.yaml` 只登记 GitHub 登录名，ChatGPT 指挥官工位与 Codex worker 工位**无机器载体**
  - 生产部署与真实计费 `NOT_AUTHORIZED`；G3–H4 `PLAN_ONLY`
- **归档时间**：2026-11-12

### [FPF2-GATE-PROBE-20261112] 分支保护 `required_approving_review_count` 可达性实测（一次性探针）
- **结论**：`FAIL_CLOSED` —— GitHub 原生 `required_approving_review_count=1` 在当前身份结构下**不可达**；已回滚 `count=0`，未留死锁
- **探针**：PR #86 `fpf/gate-probe-20261112`（head `84a5c0b9`，仅新增一个临时文档），验证后关闭并删除分支与 worktree
- **实测序列**：基线（`count=0` + reviewer2 APPROVED）→ `mergeStateStatus=CLEAN`；PATCH `count=1` 后 → `BLOCKED` / `reviewDecision=REVIEW_REQUIRED`；回滚 `count=0` 后 → 恢复 `CLEAN`
- **根因**：`GET /repos/.../collaborators/fpf-reviewer-huangzuomin[bot]/permission` 返回 `{"permission":"none"}`，review 的 `authorAssociation=NONE`。GitHub 原生 required review 只统计**具备仓库写权限**身份的批准；App 安装身份不满足
- **附带排除**：`.github/CODEOWNERS` 全部自指 `@huangzuomin`，若在 `count=1` 同时保留 `require_code_owner_reviews=true`，将要求作者批准自己的 PR → 必然永久死锁；故收紧尝试时该项显式置 `false`
- **回滚后稳定配置**：`count=0`、`dismiss_stale_reviews=true`、`require_code_owner_reviews=true`（`count=0` 下不生效）、`require_last_push_approval=false`、required checks `validate` + `validate-card`（`strict=true`）、`enforce_admins=true`、禁 force push / 禁删除
- **证据**：`.fpf-runtime/evidence/20261112-gov-doc-profile/GATE-PROBE-20261112.md`（未跟踪）
- **待负责人裁定**：① 机器账号方案（write 协作者，`count=1` 可达但引入长期人格式凭据）；② 平台门禁为准（维持 `count=0`，以 `validate-card` 为唯一强制点，并改写 §8.7.2 该条）；③ 重构 CODEOWNERS 指向真实非作者账号后与 ① 组合
- **NOT_RUN / 边界**：本轮只验证 App 身份；机器账号方案未创建、未验证
- **归档时间**：2026-11-12

### [FPF2-G3-20261112] 凭据与身份边界：确定性密钥扫描 + 私钥迁出工作区
- **目标**：把"零跟踪密钥"升级为"零工作区私钥 + 三层扫描"，并留下可核验的轮换账簿
- **代码提交**：`6cac312c27a8c74482f7e89421efa3227f270c8d`
- **主干合并**：`1475f6b40002c32b351f336ec20f597e5f9aa999`（PR #89，merge commit）
- **独立 QA**：Run `43066178254` / Artifact `13876241752` / `evidence_manifest_sha256=e2fcfedb262e6debf0d8b4651725d7d20e4634098dbe5168d9fa30d2ebcf3f17`，`task_id=FPF2-G3`、`tested_sha=6cac312c`、`runner_sha`=`qa_contract_sha`=`952accfd`、16 项 PASS
- **独立 Review**：`5862645744`（`fpf-qa-bot-huangzuomin[bot]`，含 `QA_RESULT`，钉 `6cac312c`）+ `5862650215`（`fpf-reviewer-huangzuomin[bot]`，钉同一 head，承载负责人 2026-11-12 授权）
- **变更范围**：`packages/fpf_gates/secret_scan.py`（离线确定性扫描器，5 类规则 + 64 位 hex 种子上下文规则）、`packages/fpf_gates/install_hooks.py`（生成 `.githooks/pre-commit`）、`.github/workflows/secret-scan.yml`、`tests/test_secret_scan.py`（13 用例，含真实 git 仓库中 hook 阻断暂存密钥）、`docs/security/CREDENTIAL-BOUNDARY.md`
- **操作侧事实**：issuer 私钥 `k_stage_alpha_2026_11` 于 `2026-11-11T05:44:17Z` 吊销、新 key `k_stage_alpha_2026_11_r1` 于 `2026-11-11T05:40:12Z` 生成，存于 `%LOCALAPPDATA%\FPF\secrets`（仓库外）；两个 bot App 私钥同迁出，工作区 `.fpf-runtime/credentials/` 已空，两身份 token 均验证可铸造
- **扫描证据**：跟踪文件 0 命中；`git log --all --patch` 459 个 diff / 35,554 新增行，2 命中且均为 AWS 厂商占位值
- **NOT_RUN / 边界**：
  - 验收标准 5 为 **`PARTIAL`**：工作区零命中已达成，但私钥仍是磁盘明文（仓库外 ACL 目录），**未**进 OS 凭据库；运行时短时令牌属阶段 3 Credential Broker
  - Library profile 不执行测试套件，新增 13 项测试由 `validate` check run 独立执行（224 passed），不在 QA artifact 内（已写入 `QA_RESULT.findings.p1`）
  - `secret-scan` 尚未加为 required check；`install_hooks.py` 未在本机执行（会遮蔽现有 `.git/hooks/pre-push`）
  - 生产部署与真实计费 `NOT_AUTHORIZED`；G4–H4 `PLAN_ONLY`
- **归档时间**：2026-11-12

### [FPF2-G2-C4-20261112] 强制点裁定：`validate-card` 为唯一强制点
- **目标**：把 G2 的 review-count 缺口从"配置 `count=1`"改为有书面理由与残余风险清单的裁定，并拆除哑开关陷阱
- **代码提交**：`2493d10a2ea99ba60d46dd3646a8af560a19e3e6`
- **主干合并**：`68f38b85205bd2437b99f82dfb0f938655e63fd0`（PR #90，merge commit）
- **独立 Review**：`5867000430`（`fpf-reviewer-huangzuomin[bot]`，APPROVED，钉 `2493d10a`，承载负责人 Phase C4 裁定原文）
- **变更范围**：`docs/roadmap/FPF-2.0-STANDARDIZATION-ROADMAP.md` §8.7.2 重写为五节（现状证据 / 语义强度对比 / 选项否决理由 / 残余风险与缓解 / 验收标准）
- **设置操作（仓库设置，非代码）**：`require_code_owner_reviews` `true` → **`false`**；`required_approving_review_count` 维持 `0`；required checks（`validate` + `validate-card`，`strict=true`）与 `enforce_admins=true` 未改动。前后快照：`.fpf-runtime/evidence/20261112-c4-forcing-point/protection-{before,after}-20261112T1730Z.json`
- **裁定要点**：① `count=0` 下原生 review 计数惰性，合并事实由 required checks 决定；② `validate-card` 校验身份链（作者排除、head 钉定、`QA_RESULT`、run actor、artifact digest、第二工位、自授权拒绝），严格覆盖"计数"；③ 否决机器 USER、App 承担 required review、重构 CODEOWNERS 三条路径；④ `require_code_owner_reviews=true` 与 `count>=1` 叠加会要求作者自批，构成哑开关陷阱
- **事实纠正**：工单所称"PR #67/#78 零 review 合并先例"不成立——API 实测 #67 有 5 条 review、#78 有 1 条；可成立的表述是这些 review 在 `count=0` 下只对 `validate-card` 有意义
- **NOT_RUN / 边界**：未验证"机器 USER + write 协作者"路径（已否决，不实施）；G3–H4 中 G4–H4 维持 `PLAN_ONLY`
- **归档时间**：2026-11-12

### [FPF2-G4-REDUCER-01] G4 事件驱动状态归约（PROJECTION_ONLY）
- **目标**：把"状态靠人手写"改为"事件归约产生"，不新增第二套状态机，复用 §4.1 Reconciliation Protocol
- **代码提交**：`2aec8763b2d87550982e5976a904860ed91d45ca`（PR #92 head）
- **主干合并**：`feaafd3701cba9c787c550f78998d529b086bb18`（PR #92，merge commit）
- **变更范围**：`packages/fpf_coordinator/dispatch/**`（events / reducer / journal / ledger / claims / authorization / fact_source / publish_gate / poller / github_source / reconcile + `state-ledger.json`）、`.github/workflows/state-{project,project-publish,audit,reconcile,claim,claim-trigger}.yml`、`packages/fpf_policy/pr_gate.py`（仅改名逃逸路由 A-02）、`tests/**`（31 路径，+7047 行）
- **独立 QA**：Run `43183534549` / Artifact `13927866728` / ZIP digest `sha256:66b360eb…` / `evidence_manifest_sha256=4ebbd8cf51ba2ce0a7d880dbf18c0e48d509cecf6b60b6e7a33b31b4107ba0cb`，18/18 PASS，绑定 `tested_sha=2aec876`
- **独立 Review**：`5871448257`（`fpf-qa-bot-huangzuomin[bot]`，含 `QA_RESULT`，钉 `2aec876`）+ `5871450948`（`fpf-reviewer-huangzuomin[bot]`，钉同一 head，承载 `WO-20261112-g4-final-remediation` / `WO-20261112-gate-anchor-fix` 授权原文）
- **语义裁决链**：R7–R11 五轮设计复裁 + FINAL / FINAL-R2（`CHANGES_REQUIRED`，B01/B02/B03）+ FINAL-R3（B03 CLOSED、B01/B02 OPEN、门禁锚定 `ACCEPTED_AS_GOVERNANCE_HARDENING`）+ FINAL-R4（`verdict: PASS`，B01/B02/B03 全 CLOSED，`merge_now_ok: false` 仅因平台审批未完成）
- **裁决纠正的两处真实缺陷**：①`fact_source._page` 过滤而非拒绝非对象记录（100 条丢 1 条会被读成"最后一页"提前结束采集）→ 改为 `EVENT_SOURCE_MALFORMED`；②`run_gate` 用候选自身归约顺序当基准（自证）→ 改为 `compare_observation_to_candidate(observation.events, artifact["events"])`，多重性先于位置判定
- **四个平台事实（本切片实测入 main）**：`expires_at` 被解析为 `datetime`；`refs/fpf-probe/**` 不落盘（改用 `refs/tags/`）；`GET /git/ref` 与 `matching-refs` 须省略 `refs/` 前缀；`POST /git/refs` 返回 201 后立即 GET 可能 404（读后写重试）
- **并发实测（P1-D06-01）**：可信 main `31dc9226` 双 dispatch，run `43166501236`=1×201/35×422、run `43166501974`=0×201/36×422，请求窗口交集 **78.374s**，72 次请求恰 1 次 201，唯一 winner `7134ae093a42ea9233038783446131943b5a3cf9`；相关代码在 `6e2cbad` 上逐字节未变
- **基线既有失败（P1-FINAL-QA-01）**：`5b4bfa2` 复跑 `test_standard_2_0` = 1 failed / 2 passed，根因 #89 遗留，非本 PR 引入
- **NOT_RUN / 边界**：
  - `production_claim_e2e` **NOT_RUN**（真实默认分支调度未跑）；`MERGED` 生命周期由记账 PR 合并事件收尾
  - 生产部署与真实计费 **NOT_AUTHORIZED**；H1–H4 **PLAN_ONLY**；`sovereign_override` 零使用
  - G3 残留移交：私钥仍在仓库外磁盘明文（ACL 目录），OS 凭据库属阶段 3
- **归档时间**：2026-11-12

### [FPF2-GATE-ANCHOR-01] 门禁证据要求表锚定 base（治理收紧）
- **目标**：关闭"被审查者自定义本次审查标准"的漏洞，并解除由它造成的 B03 自指死锁
- **代码提交**：`de893a4e2730b0b4be8eb1749fcc10c6152950ef`（PR #101 head）
- **主干合并**：`19ca7dc1cad2dd88eaf9f95ad7ba8adba7361c02`（PR #101，merge commit）
- **变更范围**：`.github/workflows/validate-handoff-cards.yml`（base 恢复行增加 `packages/fpf_coordinator/`）、`tests/test_gate_anchor.py`（5 项：workflow 接线、head 缩表不生效、head 扩表不对本 PR 生效、anchor 幂等且与 base 字节一致、base 缺包 fail-closed）
- **独立 QA**：Run `43180174197` / Artifact `fpf-qa-de893a4…` / `evidence_manifest_sha256=1b75d29809de83ff710791f6dee681b67f7795b2b023f3b159760c9129a6a3cb`，16/16 PASS
- **独立 Review**：`5871139592`（QA bot）+ `5871142025`（reviewer2，承载 `WO-20261112-gate-anchor-fix` 原文）
- **死锁实测（修复前）**：PR #100 的 head 要求 18 项、artifact 由 main 采集器生成仅 16 项，用其唯一真实 artifact 跑真实门禁 → `omitted mandatory evidence items: ['EVID-35','EVID-36']`；即"新增强制证据项"不可门禁
- **同一根因的另一方向（活体漏洞）**：head 可缩小 `_LIB` 自行降低验收门槛，无需任何审批
- **修复后**：同一 PR #100、同一 artifact → `GATE_PR independently QA verified and dual-approved`；随后 PR #100 合并（`6e2cbad`），Library 强制集 16 → 18
- **裁决认定**：QA 总指挥 FINAL-R3/R4 均裁 `ACCEPTED_AS_GOVERNANCE_HARDENING`，建议作为 G2 宪制强制力输入；原则 = "被审查者可以提出修改规则，但不能自行决定本次审查适用什么规则"
- **NOT_RUN / 边界**：未改 `qa_collector.py` / `pr_gate.py` / `qa_artifact.py`；未改 `REQUIRED_PROFILE_EVIDENCES` 语义（仅后续 PR #100 生效）；生产/计费 `NOT_AUTHORIZED`
- **归档时间**：2026-11-12
