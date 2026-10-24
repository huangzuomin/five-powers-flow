# FPF 在 Claude Code 中的工程落地指南 (Claude Code Implementation Guide)

> **核心洞见**：分权制衡若只依赖提示词（Prompting），就是把安全建立在“祈祷”之上。  
> Claude Code 提供了原生只读子代理工具集硬剔除与 `PreToolUse` Hook 机制，可将 FPF 协议从“道德倡议”升级为“机械强制”（Mechanical Enforcement）。

---

## 一、 为什么在 Claude Code 中必须机械强制？

在 FPF 体系中：
- **QA 角色**：严禁修改被测业务代码；
- **DEV 角色**：严禁修改正式项目地图（`PROJECT-MAP.md`）；
- **地图总控**：仅允许修改 `docs/coordination/PROJECT-MAP.md`。

如果你仅仅在 `CLAUDE.md` 或 Prompt 里写“请不要修改某文件”，大模型在高强度推理或犯抽时依然会调用写工具。而在 Claude Code 中，我们可以通过两道防线物理锁死这一红线。

---

## 二、 第一道防线：利用原生只读子代理 (Built-in Read-Only Subagents)

Claude Code 的 `Explore` 和 `Plan` 子代理类型，其工具集里**硬性排除了 `Edit`、`Write`、`NotebookEdit`**：

| 角色 | 推荐 Claude Code 模式 | 原生工具集边界 | 强制力保证 |
| :--- | :--- | :--- | :--- |
| **③ DEV 总指挥** | `Plan` 子代理 | 只读分析、只能输出建议与规划，无写工具 | ✅ 平台硬剔除 |
| **④ QA 总指挥** | `Explore` 子代理 | 仅能读取、检索、运行只读审查，无代码写权限 | ✅ 平台硬剔除 |
| **DEV 编码工位** | 独立 Worktree 实例 | 完整读写，但受 PreToolUse Hook 拦截 | ⚠️ Hook 拦截 |
| **QA 独立工位** | 独立隔离 Worktree | 仅测试代码目录可写，业务源代码只读挂载 | ✅ 文件系统+Hook |

---

## 三、 第二道防线：PreToolUse Hook 物理拦截

通过在项目 `.claude/settings.json` 中配置 `PreToolUse` 钩子，可以在模型调用工具之前执行脚本。若违反协议，直接以非 0 退出码拒绝执行。

### 1. 拦截 DEV 工位窜改项目地图
在 DEV 研发工位配置 Hook：
```json
{
  "hooks": {
    "preToolUse": "python packages/fpf-gates/hook_guard_dev.py"
  }
}
```

`hook_guard_dev.py` 逻辑：
```python
import json, sys

# Claude Code 传入当前准备调用的工具信息
payload = json.load(sys.stdin)
tool_name = payload.get("tool_name")
tool_input = payload.get("tool_input", {})
file_path = tool_input.get("file_path", "")

# 铁律：DEV 严禁触碰项目地图
if tool_name in ("Edit", "Write") and "PROJECT-MAP.md" in file_path:
    sys.stderr.write("[FPF CRITICAL BLOCK] DEV 工位严禁修改 PROJECT-MAP.md！这是地图总控的专属法定权力。\n")
    sys.exit(1) # 非 0 退出，物理阻断工具执行

sys.exit(0)
```

### 2. 拦截 QA 工位修改业务代码
在 QA 工位配置 Hook：
```python
import json, sys

payload = json.load(sys.stdin)
tool_name = payload.get("tool_name")
tool_input = payload.get("tool_input", {})
file_path = tool_input.get("file_path", "")

# QA 严禁触碰除 tests/ 和 docs/evidence/ 以外的业务代码
if tool_name in ("Edit", "Write"):
    if not (file_path.startswith("tests/") or file_path.startswith("docs/evidence/")):
        sys.stderr.write(f"[FPF CRITICAL BLOCK] QA 工位严禁修改业务代码 {file_path}！发现缺陷请出具 QA FAIL 裁决。\n")
        sys.exit(1)

sys.exit(0)
```

---

## 四、 独立会话与 Worktree 物理隔离

不要在同一父会话中通过普通子代理交替扮演 DEV 和 QA，因为子代理共享父会话的权限上下文。  
标准做法是：
1. 为 DEV 创建独立终端会话，进入 `_worktrees/dev-001`；
2. 为 QA 创建独立终端会话，进入 `_worktrees/qa-001`；
3. 两者通过 GitHub PR 与 Issue 交换卡片，实现物理级的真正隔离。
