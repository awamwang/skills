# 查询

用脚本列出并对比三处技能来源。**禁止**用 AI 逐步 `gh` / 手扫目录代替本脚本。

## 三处来源

| 代号 | 含义 | 数据怎么来 |
|------|------|------------|
| **组织** | GitHub 组织 `awam-skills` 下的技能仓 | GitHub API（`gh` token） |
| **索引** | 本索引仓远程 README 收录的技能 + 仓内 `skills/*/SKILL.md` | 优先 `origin/*/README.md`，否则本地；叠加 `skills.overrides.json` |
| **本机** | `%USERPROFILE%\.agents\skills\awam\`（macOS/Linux: `~/.agents/skills/awam/`）下子目录 | 扫本地目录 |

对比键：小写；若名称以 `-skill` 结尾则去掉该后缀再对齐（`-skills` 不剥）。

## 何时用

用户要：查组织有哪些技能仓、索引仓收录了什么、本机 awam 装了什么，或三者存在性对比 / 缺口。

## 步骤

1. 在索引仓根（或任意能解析到本脚本的路径）执行：

```bash
python skills/awam-skills/scripts/query_skills.py
```

Windows PowerShell 示例：

```powershell
python "$PWD\skills\awam-skills\scripts\query_skills.py"
```

2. 把脚本 stdout（Markdown 表 + 分源列表）原样或略整理后回复用户；**不要**再手工复跑 API。
3. 若报 `org:` API 错误：确认 `gh auth login` 或环境变量 `GH_TOKEN` / `GITHUB_TOKEN`。
4. 若本机列为空：确认目录是否存在；可用 `--local-dir` 覆盖。

## 常用参数

| 参数 | 作用 |
|------|------|
| （默认） | 对比表 + 三分源列表 |
| `--only compare` | 只要对比表 |
| `--only org` / `index` / `local` | 只要单源列表 |
| `--format json` | JSON（给后续脚本或精确字段） |
| `--no-remote` | 索引只用本地 README |
| `--local-dir <path>` | 覆盖本机 awam 目录 |

## 校验

- [ ] 已运行 `query_skills.py`，未用手搓列表替代
- [ ] 回复含对比表（或缺省原因：鉴权失败等）
- [ ] 未改 `skills.overrides.json` / 未跑 `sync_skills.py`（查询只读）

## 缺口怎么读

| 提示 | 常见含义 |
|------|----------|
| 组织有、索引无 | 仓已建但未进 overrides / README 未同步 |
| 索引有、组织无 | 个人 topic 仓或仅 overrides；流程 Skill `awam-skills` 除外 |
| 组织有、本机 awam 无 | 未链到 `~/.agents/skills/awam/`（可能装在 skills 根目录） |
| 本机有、组织无 | 本地草稿 / 未发布组织仓 |
| 本机目录缺 SKILL.md | 文件夹在，但还不是完整 Skill |
