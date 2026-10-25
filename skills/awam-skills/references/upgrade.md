# 升级（发版升号）

对发布规划内的技能做 **semver 升号 + 回写 repos 版本字段**。权威 `version` 在技能仓 `SKILL.md` frontmatter；本机 `docs/repos.json` 各条目保存管理用快照（模板见 `docs/repos.example.json`，文件 gitignore）。

**禁止**用手改 version 行或只改 repos 字段代替本脚本。

## 与相邻流程的分工

| 流程 | 做什么 | 不做什么 |
|------|--------|----------|
| **升级**（本页） | bump frontmatter、刷新/回写 `repos.json` 版本字段 | 不 commit/push；不替你发平台 |
| **发布漂移** | `check_publish_drift.py` 看本地相对已发布 commit 是否前进 | 不升 version |
| **平台发布** | `release.py` / 各 `publish_*.py` | 假设 version 已定好且内容已 push |
| **查询** | 组织 / 索引 / 本机扫描根对比 | 不改 version |

升号后仍须：用户确认 → commit + push 技能仓 →（需要时）preflight → release。

## 何时用

用户要：升级某技能版本、查看管理中技能的版本列表、刷新 repos 版本字段、升号后再发平台。

## 步骤

1. **在索引仓根执行**（需能读 `docs/publishing-plan.json`、读写 `docs/repos.json`）。

2. 按意图选命令：

```bash
# 只读列出 repos 中的版本字段（不扫本机）
python skills/awam-skills/scripts/upgrade_skill.py --list

# 按 plan 从本机克隆重刷 repos 版本字段，并同步 repos.example.json
python skills/awam-skills/scripts/upgrade_skill.py --refresh

# 升版（改技能仓 frontmatter + 回写 repos 版本字段；不提交）
python skills/awam-skills/scripts/upgrade_skill.py --skill <key> --part patch
python skills/awam-skills/scripts/upgrade_skill.py --dir <技能仓> --to 1.2.0
python skills/awam-skills/scripts/upgrade_skill.py --skill <key> --part minor --dry-run

# 升版后若工作区已干净则衔接 release（刚 bump 未提交时会提示先 commit）
python skills/awam-skills/scripts/upgrade_skill.py --skill <key> --part patch --release
```

3. 把脚本输出中的建议提交信息与下一步原样告知用户；**不要**在未明确要求时替用户 commit / push / release。
4. 用户完成技能仓 commit + push 后，若要发平台：走 [platforms.md](platforms.md) / `release.py`。
5. `repos.json` 变更**不要提交**（已 gitignore）；`repos.example.json` 随 `--refresh` 更新后可入库。

## 常用参数

| 参数 | 作用 |
|------|------|
| `--list` | 列出 `repos.json` 版本字段 |
| `--refresh` | 全量重刷版本字段 + 更新 example |
| `--skill <key>` | 按 `publishing-plan.json` 的技能 key（需 `repos.json` 有 path） |
| `--dir <path>` | 按技能仓本地路径 |
| `--part major\|minor\|patch` | semver 段递增 |
| `--to x.y.z` | 设为目标版本 |
| `--dry-run` | 只打印不写盘 |
| `--release` | 升版后尝试调用 `release.py` |
| `--release-args "..."` | 传给 `release.py` 的额外参数 |

底层仍可单独用 [bump_version.py](../scripts/bump_version.py) 只改 frontmatter（**不**回写 repos）；管理流程优先 `upgrade_skill.py`。

## 校验

- [ ] 已运行 `upgrade_skill.py`，未手改 version / repos 版本字段代替
- [ ] 未擅自 commit / push / 平台发布（除非用户明确要求）
- [ ] 未提交 `docs/repos.json`

## repos 版本字段

```json
{
  "<plan-key>": {
    "path": "G:/Projects/19AI/skills/...",
    "version": "x.y.z",
    "name": "<frontmatter name>",
    "repo": "awam-skills/<repo>",
    "version_updated": "YYYY-MM-DD"
  }
}
```

无本机克隆或读不到 SKILL.md 时：`version` 为 `null`，并带 `version_reason`（不编造版本号）。
