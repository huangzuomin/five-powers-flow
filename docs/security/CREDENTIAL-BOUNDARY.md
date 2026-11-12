# 凭据与身份边界（G3）

本文件记录 FPF 的密钥面、轮换事实与强制层。它是**事实账簿**，不是授权文件：
任何轮换、吊销或迁移都必须同时留下可核验的证据，否则按 `NOT_RUN` 记录。

## 一、强制层（三层，缺一层即降级）

| 层 | 载体 | 强度 | 状态 |
|---|---|---|---|
| 平台原生 | GitHub secret scanning + push protection | 不可绕过，但只认厂商格式 | `enabled`（仓库设置实测） |
| CI | `.github/workflows/secret-scan.yml` | 可绕过（需改 workflow），但每次 PR 必跑 | 本切片新增 |
| 本地 | 生成的 `.githooks/pre-commit` → `packages/fpf_gates/secret_scan.py --staged` | 可 `--no-verify` 绕过 | 本切片新增 |

扫描器（`packages/fpf_gates/secret_scan.py`）是**确定性的、离线的**：不联网、
不读取指定路径以外的材料、输出只含命中位置与规则名，不回显密钥全文（截断至 120 字符）。
钩子正文由 `packages/fpf_gates/install_hooks.py` 在安装时写出，仓库里不单独跟踪
`.githooks/pre-commit`——原因见第七节。

### 规则集

| 规则 | 目标 |
|---|---|
| `PEM-PRIVATE-KEY` / `OPENSSH-PRIVATE-KEY` | PEM 私钥块 |
| `AWS-ACCESS-KEY` | `AKIA` + 16 位大写字母数字 |
| `GITHUB-TOKEN` / `GITHUB-FINE-GRAINED-PAT` | `ghp_`/`gho_`/`ghs_`/`ghu_`/`ghr_`、`github_pat_` |
| `SLACK-TOKEN` | `xox[baprs]-` |
| `HEX64-KEY-CONTEXT` | 同一行出现 64 位十六进制**且**出现 key/seed/secret 等词（Ed25519 种子） |

### 抑制与白名单

- 行内标记 `# fpf-secret-scan: allow <理由>` 可抑制该行，理由必须写在同一行。
- `ALLOWED_EXACT` 只保留厂商文档公布的占位值（当前仅 AWS 文档示例），刻意保持极小，
  避免把真实凭据"认成示例"。

## 二、密钥清单与当前位置

| 材料 | 标识 | 位置 | 是否在仓库/工作区 |
|---|---|---|---|
| Inflow issuer 私钥 | `k_stage_alpha_2026_11_r1` | `%LOCALAPPDATA%\FPF\secrets\inflow-issuer-private-key.hex` | 否 |
| QA bot App 私钥 | `fpf-qa-bot-huangzuomin` | `%LOCALAPPDATA%\FPF\secrets\fpf-qa-app.pem` | 否（2026-11-12 迁出） |
| reviewer2 App 私钥 | `fpf-reviewer-huangzuomin`（App `5713253` / installation `180902777`） | `%LOCALAPPDATA%\FPF\secrets\fpf-reviewer-app.pem` | 否（2026-11-12 迁出） |
| collector token | `col_stage_alpha` | `.inflow-setup/collector_token.txt` | 是，但被 `.gitignore` 覆盖且未跟踪 |

`git ls-files` 对这些路径零命中；`.gitignore` 第 39–42 行（PR #67 `a7ac512` 入库）
覆盖 `.inflow-setup/`、`secrets/`、`*.hex`、`.fpf-runtime/`。

## 三、轮换记录

### `k_stage_alpha_2026_11` → `k_stage_alpha_2026_11_r1`

| 字段 | 值 |
|---|---|
| 触发原因 | 私钥以未加密形式落盘于工作区 `.inflow-setup/`，按**已暴露**处理 |
| 轮换时间 | `2026-11-11T05:40:12Z` |
| 旧 key id | `k_stage_alpha_2026_11` |
| 旧 key 吊销时间 | `2026-11-11T05:44:17Z` |
| 新 key id | `k_stage_alpha_2026_11_r1` |
| 新公钥指纹（SHA-256 前 16 位） | `c1a9371fb1a038c5`（对 64 位十六进制公钥串取 SHA-256） |
| 私钥迁移目标 | `%LOCALAPPDATA%\FPF\secrets`（仓库外，NTFS ACL 限制） |
| 操作者 | `huangzuomin`（记录来源为本机 `summary.json`；该文件**不含** operator 字段，此处按仓库所有者归属，未经独立签名确认） |

### bot App 私钥迁出工作区（2026-11-12）

- 迁移前：`.fpf-runtime/credentials/{fpf-qa-app,fpf-reviewer-app}.{json,pem}`。
- 迁移后：同四文件位于 `%LOCALAPPDATA%\FPF\secrets\`，工作区目录已清空。
- 校验：两个身份的 installation token 均从新路径成功铸造（`ghs_` 前缀，长度 383），
  且解析出的 `META_PATH` / `KEY_PATH` 均在工作区之外。
- 代码侧：`gh_app.py` 默认目录改为 OS 本地应用数据目录；仅当新路径缺失时回退到
  旧目录，保证迁移期不断线。

## 四、吊销列表

| key id / 主体 | 吊销时间 | 原因 | 证据 |
|---|---|---|---|
| `k_stage_alpha_2026_11` | `2026-11-11T05:44:17Z` | 明文落盘暴露 | 本机 `summary.json` |

## 五、扫描证据（2026-11-12 实测）

| 扫描 | 范围 | 结果 |
|---|---|---|
| 跟踪文件 | `git ls-files` 全量（含新增扫描器与测试） | **0 命中** |
| 全历史 | `git log --all --patch`，459 个文件 diff / 35,554 新增行 | **2 命中，均为 AWS 厂商文档占位值**（`tests/test_security_isolation.py`），0 条 PEM / GitHub token / PAT 命中 |
| 工作区 | `.fpf-runtime/credentials/` | **空**（4 个文件已迁出） |

## 六、未完成项（如实记录）

1. **OS 凭据库未启用**：私钥仍在磁盘上（仓库外的 ACL 限制目录），未进 Windows
   DPAPI / Credential Manager。"工作区零命中"已达成，"OS 凭据库"未达成，故验收
   标准 5 记为 `PARTIAL`。
2. **运行时短时令牌**属阶段 3 的 Credential Broker 设计，不在 G3 范围（roadmap
   §8.7.3 边界："G3 先解决静态密钥不落盘，Broker 解决运行时短时令牌"）。
3. **pre-commit 钩子默认未安装**：需要在本机执行
   `python packages/fpf_gates/install_hooks.py`。该工具会先写出
   `.githooks/pre-commit`，列出将被 `core.hooksPath`
   遮蔽的 `.git/hooks` 条目，不静默搬移或删除。
4. **CI 中的 `secret-scan` 尚未被加为 required check**：需在分支保护里加入
   `secret-scan`，本切片不自动修改仓库设置。
5. **扫描范围以 `git ls-files` / 暂存区为准**：未 `git add` 且未跟踪的文件不在
   任何一层范围内。本次实跑已踩到该边界——本地在 `git add` 之前验证，扫描器漏掉了
   自己的规则定义行，由 CI 的 `secret-scan` 抓到（LESSON-013）。先 add、再验证。

## 七、为什么扫描器放在 `packages/fpf_gates/`

门禁的 `POLICY_CHANGE` 路由（`pr_gate._policy_scope`）只接受三类路径：
受保护前缀（`.github/`、`.fpf/`、`schemas/`、`packages/` 等）、`docs/`、`tests/`、
`templates/`，以及少数仓库根文件。`tools/` 与 `.githooks/` **不在**这三类里。

后果是实测到的路由死锁：

- 含 `.github/workflows/` 的 PR → `POLICY_CHANGE` → `GATE_PR`，但同一 PR 里出现
  `tools/security/...` 会报 `POLICY_CHANGE contains unrelated application files`；
- 改用 `DEV_HANDOFF` → `CODE_PR`，又会因 `.github/` 属受保护路径报
  `CODE_PR modifies protected governance paths`。

把扫描器与安装器放进受保护的 `packages/fpf_gates/`，钩子正文改为安装时生成，
整个切片就落在同一类路径上，可一单走 `GATE_PR`。这是路由约束导致的落点选择，
不是包归属判断。
