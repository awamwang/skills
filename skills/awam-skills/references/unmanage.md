# 移出管理

把技能从本索引仓的**管理面**拿掉：不再出现在发布规划、本机 repos 映射、发布状态与升级/漂移流程中。

**不**删除本机技能目录，**不**改技能仓 git，**不**改索引 `README.md`（仍由 Actions 同步）。默认也**不**改 `skills.overrides.json`。

**禁止**手删 JSON 条目代替本脚本。

## 何时用

用户要：移出管理、不再管理某技能、从规划里拿掉、取消纳入升级/发布编排。

## 步骤

1. 在索引仓根执行：

```bash
python skills/awam-skills/scripts/unmanage_skill.py --skill <key>
python skills/awam-skills/scripts/unmanage_skill.py --skill a --skill b
python skills/awam-skills/scripts/unmanage_skill.py <key1> <key2>
python skills/awam-skills/scripts/unmanage_skill.py --skill <key> --dry-run
```

2. 把脚本输出原样告知用户；**不要**在未明确要求时 commit 索引仓。
3. `docs/repos.json` 已 gitignore，**勿提交**；`publishing-plan.json` / `publishing-plan.md` / `repos.example.json`（及可选的 state / overrides）可入库，需用户确认后再提交。

## 会改什么

| 文件 | 行为 |
|------|------|
| `docs/repos.json` | 删除该 key |
| `docs/publishing-plan.json` | 删除 `skills.<key>` |
| `docs/publishing-state.json` | 若有则删除该 key |
| `docs/repos.example.json` | 按剩余 plan 重写 |
| `docs/publishing-plan.md` | 跑 `plan_skills.py` 刷新（可用 `--no-refresh-view` 跳过） |
| `skills.overrides.json` | **仅** `--also-overrides` 时删除匹配的 `owner/repo` 或裸 key |

## 常用参数

| 参数 | 作用 |
|------|------|
| `--skill <key>` / 位置参数 | 规划 key（可多个） |
| `--dry-run` | 只打印命中处，不写盘 |
| `--also-overrides` | 同时清 overrides |
| `--no-refresh-view` | 不刷新 `publishing-plan.md` |

## 校验

- [ ] 已跑 `unmanage_skill.py`，未手改 JSON 代替
- [ ] 未擅自删除本机技能目录 / 未擅自 commit
- [ ] 未提交 `docs/repos.json`

## 与相邻流程

| 流程 | 关系 |
|------|------|
| **升级** | 移出后不再出现在 `--list` / `--refresh` 范围 |
| **发布漂移** | 移出后不再检测该技能 |
| **查询** | 本机扫描仍可能列出目录；管理对比以 plan/repos 为准 |
| **同步 README** | 若仍在组织仓或 overrides，Actions 仍可能收录；要从索引消失需另改 overrides / 组织仓 Topics（可用 `--also-overrides`） |
