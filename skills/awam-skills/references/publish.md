# 发布

把技能仓公开到 GitHub，并完成索引收录。README 只交给 Actions 写。

## 前置

- 技能仓本地内容已可公开（`SKILL.md` 齐备）
- 索引仓可写（本仓库根，含 `skills.overrides.json`）
- `gh` 已登录

确认或推导：

| 项 | 来源 |
|----|------|
| `repo_name` / `full_name` | remote 或命名规则 → `awam-skills/<repo_name>` |
| skill `name`、description | 技能仓 `SKILL.md` frontmatter（嵌套则读 `skills/<name>/SKILL.md`） |
| **category** | **必须问用户**：选 `skills.overrides.json` 已有 `categories[].id`，或让用户给新分类的 `id` / `title` / `topics` |
| 中文简介 | 默认用 frontmatter `description`；用户要求改写时以用户文案为准 |

## 步骤

### 1. 技能仓：提交与 push（按需）

- 若工作区有未提交且用户同意提交：按该仓 awam-git 规范 commit（仅用户明确要求时 commit）。
- 检测远程是否已有提交：

  ```bash
  git ls-remote --heads origin main
  ```

  - **空**：`git push -u origin main`（或当前默认分支）
  - **已有**：只 push 当前落后的本地提交（用户要求时）；不要强推

### 2. Topics 与 description

```bash
gh repo edit "awam-skills/<repo_name>" --add-topic skill --add-topic skills --description "<description>"
```

若用户选定了分类且该分类有 `cat-*` 类 topic，一并 `--add-topic`。

### 3. 更新索引仓 overrides

在**索引仓**编辑 `skills.overrides.json`：

1. 若需新分类：追加到 `categories`（`id`、`title`、`topics`）。
2. 在 `overrides` 增加或更新：

```json
"awam-skills/<repo_name>": {
  "category": "<category-id>",
  "description": "<中文简介>"
}
```

3. **不要**运行 `scripts/sync_skills.py`。
4. 仅在用户明确要求时，在索引仓 commit + push `skills.overrides.json`（可含本 Skill 其它已改文件）。push 后 Actions 会因 path 过滤自动同步 README。

### 4. 等待 / 核对照索引

- 默认等 Actions；可用 `gh run list --workflow "Sync Skills Catalog" --limit 3` 查看状态。
- 若迟迟未跑：在索引仓 `gh workflow run "Sync Skills Catalog"`，仍不要本地写 README。
- 若发现本地与线上同时有人改 README：停手，以 Actions 结果为准，必要时 `git pull --rebase`。

### 5. 更新发布规划

在索引仓 `docs/publishing-plan.json` 把该技能 `status.github` 置 `done`，运行：

```bash
python skills/awam-skills/scripts/plan_skills.py
```

刷新 `docs/publishing-plan.md`。如需继续发布到第三方平台（LobeHub / 魔搭 / 豆包 / ClawHub / AgentPowers），走 [platforms.md](platforms.md)，完成后逐平台把 `status` 置 `done` 并再次刷新。

## 禁止

- 本地执行 `python scripts/sync_skills.py` 作为发布步骤
- 为「看起来更快」同时本地同步又 push overrides
- 在平台之外另造市场 / 清单文件（`skill.json`、ClawHub 包等）；第三方平台发布统一走 `platforms.md`
- 把本索引仓的 `skills/awam-skills` 再发布成组织下另一个技能仓

## 校验

- [ ] `awam-skills/<repo_name>` 公开可访问，含最新 `SKILL.md`
- [ ] Topics 含 `skill`、`skills`
- [ ] `skills.overrides.json` 已有对应条目与正确 `category`
- [ ] 未本地改写 `README.md`（除非用户单独要求且理解会被 Actions 覆盖）
- [ ] Actions 同步成功或已手动 `workflow_dispatch`
- [ ] `docs/publishing-plan.json` 的 `status.github` 已置 `done`；视图已刷新
