# FPF 在 Claude Code 中的工程落地指南 (Claude Code Implementation Guide)

> **版本**：v1.2.0  
> **核心原则**：分权制衡若只依赖提示词（Prompting），就是把安全建立在“祈祷”之上。  
> Claude Code 提供了原生只读子代理工具集硬剔除与 `PreToolUse` Hook 机制，可将 FPF 协议从“道德倡议”升级为“机械强制”（Mechanical Enforcement）。

---

## 一、 双层防御架构 (Defense-in-Depth)

1. **第一层：客户端机械阻断 (Local PreToolUse Hooks & Read-Only Tools)**  
   在模型发起写操作时，毫秒级直接在本地拦截阻断，避免跑偏或污染本地文件。
2. **第二层：服务端法定防线 (Server-Side Branch Protection & CI Checks)**  
   无论客户端如何使用 `--no-verify` 或绕过 Hook，GitHub 远端的分支保护规则与强制 Status Check 绝不放行，确保主干安全绝对可靠。

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

通过在项目 `.claude/settings.json` 中配置符合官方规范的 `PreToolUse` 钩子，可以在模型调用工具之前执行脚本拦截。

### 1. 规范配置文件 `.claude/settings.json`
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python packages/fpf-gates/hook_guard_dev.py"
          }
        ]
      }
    ]
  }
}
```

### 2. 退出码协议 (Exit Code Protocol)
在 Claude Code 规范中：
- 退出码 `0`：放行，正常调用工具；
- **退出码 `2`**：**标准物理阻断**，工具调用被中止，标准错误输出（stderr）将作为错误信息回传给智能体，迫使其感知法定红线；
- 退出码 `1`：一般性脚本异常退出。

### 3. 拦截实现脚本 (`packages/fpf-gates/hook_guard_dev.py`)
该脚本已内置于本仓库：
- 标准化匹配 Windows 与 POSIX 路径分隔符与大小写；
- 遇到尝试向 `PROJECT-MAP.md` 写入时，向 stderr 输出拦截警告并返回退出码 `2`，实现严密阻断。

---

## 四、 独立会话与 Worktree 物理隔离

严禁在同一父会话中通过普通子代理交替扮演 DEV 和 QA，因为普通子代理共享父会话的权限上下文。  
标准规范操作：
1. 为 DEV 分配独立 Worktree（如 `_worktrees/dev-001`）与独立会话；
2. 为 QA 分配独立 Worktree（如 `_worktrees/qa-001`）与独立会话；
3. 两者通过 GitHub PR 与 Issue 交换结构化卡片，实现物理级的真正隔离。
