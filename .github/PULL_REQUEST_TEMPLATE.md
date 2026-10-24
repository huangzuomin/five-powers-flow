## 变更概述
请简述本次 PR 的变更内容、动机与受影响模块。

## 契约核验清单 (Checklist)
- [ ] 本 PR 严格遵守五权分立协议（未修改 PROJECT-MAP.md）
- [ ] 附带标准的 `DEV_HANDOFF` YAML 区块（40 位固定代码 SHA）
- [ ] 已在本地通过 `pre-handoff` 门禁与无污染工作树检查
- [ ] 未运行或未覆盖项已如实填入 `not_run`

## DEV_HANDOFF 区块
```yaml
handoff_version: 1
kind: DEV_HANDOFF
task_id: "XXX"
baseline_sha: ""
tested_code_sha: ""
pr_url: ""
scope: ""
changed_files: []
dev_checks: []
not_run: []
known_risks: []
state: "DEV_READY_FOR_QA"
```
